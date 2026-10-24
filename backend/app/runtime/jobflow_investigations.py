"""Durable investigator scheduling and untrusted-result validation."""

import os

from app.contracts.jobflow import InvestigationOutcome, InvestigationRun
from app.provider.jobflow import cite
from app.runtime.jobflow_policy import (
    effective_fields,
    evidence_digest,
    find,
    proposal,
    scope_digest,
)
from app.storage.jobflow import DomainError, canonical, uid


def queue_investigation(service, db, order, issue_id, mode, now, emit, question_id=None):
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


def validate_outcome(order, raw, request, *, store=None, db=None):
    outcome = InvestigationOutcome.model_validate(raw)
    if (
        outcome.revision != request["snapshot"]["revision"]
        or outcome.issue_id != request["issue_id"]
        or outcome.model_mode != request["mode"]
    ):
        raise DomainError("Investigator returned the wrong issue, revision or execution mode")
    evidence = {item.id: item for item in order.evidence}
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
    for question in outcome.questions:
        if (
            question.issue_id != outcome.issue_id
            or question.id in question_ids
            or question.status != "OPEN"
            or question.answer_id is not None
        ):
            raise DomainError("Question must be new, open and scoped to this exact issue")
        question_ids.add(question.id)
    return outcome


def apply_outcome(order, outcome, now, emit):
    issue = find(order.issues, outcome.issue_id, "Issue")
    issue.findings = outcome.findings
    issue.questions.extend(outcome.questions)
    for action in order.actions:
        if action.issue_id == issue.id and action.status in {"PROPOSED", "APPROVED"}:
            action.status = "STALE"
    owned = issue.field in effective_fields(order, now)
    # Terms establish authority. The model's recommendation alone never does.
    kinds = {"INCLUDED_FIELD"} if owned else set(outcome.recommendations)
    if not owned and "INCLUDED_FIELD" in kinds:
        kinds.remove("INCLUDED_FIELD")
        kinds.add("HUMAN_REVIEW")
    if not kinds:
        kinds.add("HUMAN_REVIEW")
    for kind in sorted(kinds):
        action = proposal(
            order,
            now,
            kind=kind,
            fields=[issue.field] if kind != "HUMAN_REVIEW" else [],
            job_ids=issue.job_ids,
            issue_id=issue.id,
            basis=(
                "Effective signed terms include this field"
                if owned
                else "Runtime-scoped proposal; independent approval required"
            ),
            citations=[
                cite(item) for item in order.evidence if item.authority == "ACCEPTED_AGREEMENT"
            ],
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
            )
    else:
        issue.state = "OPEN"
        issue.owner = "controller"
        issue.next_action = "Approve, decline or hand off the current supported proposal"
    for job in order.jobs:
        if issue.id in job.issue_ids:
            job.dispute = issue.state
    emit("finding.updated", issue_id=issue.id)
