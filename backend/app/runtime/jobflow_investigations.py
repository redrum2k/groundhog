"""Durable investigator scheduling and untrusted-result validation."""

import os

from app.contracts.jobflow import InvestigationOutcome, InvestigationRun
from app.investigation.documents import validate_citation
from app.investigation.jobflow import (
    ModelResponseError,
    assess,
    bind_question,
    scoped_sources,
    validate_question,
)
from app.runtime.jobflow_policy import (
    evidence_digest,
    find,
    proposal,
    scope_digest,
)
from app.storage.jobflow import DomainError, canonical, uid


def queue_investigation(service, db, order, issue_id, mode, now, emit, question_id=None):
    if order.base_order and order.base_order.order.order_state == "human_review":
        raise DomainError("Review requires a human decision; do not start another model call")
    issue = find(order.issues, issue_id, "Issue")
    if issue.state == "RESOLVED":
        raise DomainError("Issue is already resolved")
    if any(
        run.issue_id == issue_id and run.status in {"QUEUED", "RUNNING"}
        for run in order.investigations
    ):
        raise DomainError("This issue already has a pending investigation")
    run = InvestigationRun(
        id=uid("run"), issue_id=issue_id, revision=order.revision, status="QUEUED", mode=mode
    )
    if mode == "ANTHROPIC" and not service.available(db):
        raise DomainError(
            "Anthropic credentials, model and remaining explicit call budget required", 503
        )
    for question in issue.questions:
        if question.status == "OPEN" and (
            (
                question.agreement_version is not None
                and question.agreement_version != order.agreement.version
            )
            or (
                question.evidence_digest is not None
                and question.evidence_digest != evidence_digest(order)
            )
        ):
            question.status = "CANCELLED"
            emit(
                "question.cancelled",
                question_id=question.id,
                issue_id=issue.id,
                reason="Question evidence or agreement binding is stale",
            )
    order.investigations.append(run)
    issue.state = "INVESTIGATING"
    issue.owner = "investigator"
    issue.next_action = "Run the queued evidence investigation"
    emit("investigation.queued", run_id=run.id, issue_id=issue.id, question_id=question_id)
    request = {
        "snapshot": order.model_dump(mode="json"),
        "issue_id": issue.id,
        "mode": mode,
        "question_id": question_id,
        "evidence_digest": evidence_digest(order),
        "scope_digest": scope_digest(order, now),
    }
    if mode == "ANTHROPIC":
        # The reservation is in the domain transaction, global to this database and never refunded.
        db.execute(
            "INSERT INTO jf_model_calls VALUES(?,?,?)",
            (run.id, canonical(request), now.isoformat()),
        )
        if db.execute("SELECT count(*) FROM jf_model_calls").fetchone()[0] > int(
            os.environ["JOBFLOW_ANTHROPIC_MAX_CALLS"]
        ):
            raise DomainError("Anthropic allocation exhausted", 503)
    service.store.enqueue(db, run.id, order.id, "investigation", request)
    return {"run_id": run.id}


def validate_outcome(order, raw, request, *, store=None, db=None, now=None):
    outcome = InvestigationOutcome.model_validate(raw)
    asked = sum(len(issue.questions) for issue in order.issues)
    if outcome.questions and asked + len(outcome.questions) > 2:
        raise DomainError("The shared base case has exhausted its two-question budget")
    if len(outcome.questions) > 1:
        raise DomainError("Only one evidence question is permitted per round")
    if (
        outcome.revision != request["snapshot"]["revision"]
        or outcome.issue_id != request["issue_id"]
        or outcome.model_mode != request["mode"]
    ):
        raise DomainError("Investigator returned the wrong issue, revision or execution mode")
    if outcome.questions and (
        request.get("evidence_digest") != evidence_digest(order)
        or request["snapshot"]["agreement"]["version"] != order.agreement.version
    ):
        raise DomainError("Question request has stale evidence or agreement bindings")
    scoped = scoped_sources(order, outcome.issue_id)
    evidence = {item.id: item for item in scoped}
    question_ids = {question.id for issue in order.issues for question in issue.questions}
    finding_ids = set()
    for finding in outcome.findings:
        if finding.issue_id != outcome.issue_id or finding.id in finding_ids:
            raise DomainError("Finding belongs to another issue or repeats an ID")
        finding_ids.add(finding.id)
        if finding.status in {"SUPPORTED", "CONTRADICTED", "CONFLICTING"} and not finding.citations:
            raise DomainError("Factual findings require exact evidence citations")
        for citation in finding.citations:
            source = evidence.get(citation.source_id)
            if (
                source is None
                or citation.version != source.version
                or citation.sha256 != source.sha256
                or not citation.quote
                or citation.quote not in source.text
                or not citation.locator
            ):
                raise DomainError("Finding cites missing, stale or inexact evidence")
            validate_citation(scoped, citation)
            if citation.page is not None and citation.page < 1:
                raise DomainError("Citation page must be one-based")
            if citation.page is not None and store is not None:
                _, _, extraction = store.artifact(db, order.id, source.id)
                pages = extraction.get("pages", [])
                if citation.page > len(pages):
                    raise DomainError("Citation page does not exist in the exact source")
                page_text = pages[citation.page - 1].get("text", "")
                if page_text and citation.quote not in page_text:
                    raise DomainError("Citation text is not on the cited page")
            if citation.rectangle and (
                any(x < 0 or x > 1 for x in citation.rectangle)
                or citation.rectangle[0] >= citation.rectangle[2]
                or citation.rectangle[1] >= citation.rectangle[3]
            ):
                raise DomainError("Invalid normalized citation rectangle")
    baseline = assess(order, outcome.issue_id, now=now) if outcome.questions else None
    for index, question in enumerate(outcome.questions):
        if (
            question.issue_id != outcome.issue_id
            or question.id in question_ids
            or question.status != "OPEN"
            or question.answer_id is not None
        ):
            raise DomainError("Question must be new, open and scoped to this exact issue")
        # Old deterministic adapters have no metadata. Bind only an entirely
        # unbound legacy shape, after the request's exact snapshot was checked.
        # Partial or explicitly stale bindings are never repaired.
        if (
            outcome.model_mode == "DETERMINISTIC"
            and question.origin == "DETERMINISTIC"
            and question.predicate is None
            and question.agreement_version is None
            and question.evidence_digest is None
            and baseline.questions
        ):
            question = bind_question(order, question, baseline.questions[0].predicate)
            outcome.questions[index] = question
        if outcome.model_mode == "DETERMINISTIC" and question.origin == "ANTHROPIC":
            raise DomainError("Deterministic work cannot claim model-authored question text")
        try:
            validate_question(order, question, baseline)
        except ModelResponseError as exc:
            raise DomainError(str(exc)) from exc
        question_ids.add(question.id)
    return outcome


def apply_outcome(order, outcome, now, emit):
    issue = find(order.issues, outcome.issue_id, "Issue")
    issue.findings = outcome.findings
    issue.questions.extend(outcome.questions)
    for action in order.actions:
        if action.issue_id == issue.id and action.status in {"PROPOSED", "APPROVED"}:
            action.status = "STALE"
    baseline = assess(order, issue.id, now=now)
    allowed = {*baseline.recommendations, "HUMAN_REVIEW"}
    kinds = {kind if kind in allowed else "HUMAN_REVIEW" for kind in outcome.recommendations}
    if not kinds:
        kinds.add("HUMAN_REVIEW")
    if "HUMAN_REVIEW" not in kinds and not outcome.questions:
        for question in issue.questions:
            if question.status == "OPEN":
                question.status = "CANCELLED"
                emit(
                    "question.cancelled",
                    question_id=question.id,
                    issue_id=issue.id,
                    reason="Current accepted evidence resolved the question",
                )
    for kind in sorted(kinds):
        action = proposal(
            order,
            now,
            kind=kind,
            fields=[issue.field] if kind != "HUMAN_REVIEW" else [],
            job_ids=[
                job.id
                for job in order.jobs
                if job.kind == "ORIGINAL" and issue.field not in job.fields
            ]
            if kind == "INCLUDED_FIELD"
            else issue.job_ids,
            issue_id=issue.id,
            basis=baseline.summary,
            citations=[c for finding in baseline.findings for c in finding.citations],
        )
        order.actions.append(action)
        emit("action.proposed", action_id=action.id, issue_id=issue.id)
    open_questions = [question for question in issue.questions if question.status == "OPEN"]
    if open_questions:
        issue.owner = open_questions[0].recipient
        issue.state = "WAITING_CUSTOMER" if issue.owner == "customer" else "WAITING_INTERNAL"
        issue.next_action = open_questions[0].text
        for question in outcome.questions:
            emit(
                "question.requested",
                question_id=question.id,
                issue_id=issue.id,
                recipient=question.recipient,
                text=question.text,
                predicate=question.predicate,
                agreement_version=question.agreement_version,
                evidence_digest=question.evidence_digest,
                origin=question.origin,
            )
    else:
        issue.state = "WAITING_INTERNAL" if "HUMAN_REVIEW" in kinds else "OPEN"
        issue.owner = "controller"
        issue.next_action = (
            "Review unresolved evidence or hand off; no further question is available"
            if "HUMAN_REVIEW" in kinds
            else "Approve, decline or hand off the current supported proposal"
        )
    for job in order.jobs:
        if issue.id in job.issue_ids:
            job.dispute = issue.state
    emit("finding.updated", issue_id=issue.id)
