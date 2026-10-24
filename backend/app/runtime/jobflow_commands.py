"""Explicit command owners and application-owned business transitions."""

from datetime import UTC

from app.contracts.jobflow import (
    Amendment,
    Approval,
    Attempt,
    ChangeOrder,
    Issue,
    Job,
    Message,
    PaymentOperation,
)
from app.orders.jobflow import recognize_originals
from app.payments.jobflow import post
from app.provider.jobflow import store_evidence, validate_fields, verify
from app.runtime.jobflow_policy import (
    action_digest,
    current_action,
    effective_fields,
    find,
    invalidate,
    scope_digest,
    select_jobs,
)
from app.storage.jobflow import DomainError, canonical, uid

ROLES = {
    "correct": {"provider"},
    "accept_delivery": {"customer"},
    "open_dispute": {"customer"},
    "answer": {"customer", "controller"},
    "amend_agreement": {"customer", "provider"},
    "approve_action": {"controller"},
    "decline_action": {"controller"},
    "execute_action": {"executor"},
    "accept_change": {"customer"},
    "decline_change": {"customer"},
    "receive_payment": {"executor"},
    "fulfill_change": {"provider"},
    "accept_change_delivery": {"customer"},
    "reconcile": {"executor"},
    "handoff": {"controller"},
}


def queue_delivery(
    service,
    db,
    order,
    jobs,
    fields_by_id,
    now,
    emit,
    *,
    kind,
    outcome="SUCCESS",
    change_id=None,
    issue_id=None,
):
    cost = len(jobs) if kind != "change" else 0
    reserved = sum(attempt.cost_minor for job in order.jobs for attempt in job.attempts)
    if reserved + cost > order.agreement.correction_budget_minor:
        raise DomainError("Correction compute budget exhausted")
    if any(job.attempts for job in jobs):
        raise DomainError("One attempt per unit; failed or unknown work requires handoff/reconcile")
    operation_id = uid("execution")
    specs = []
    for job in jobs:
        attempt = Attempt(
            id=uid("attempt"),
            operation_id=operation_id,
            number=1,
            status="QUEUED",
            input_artifact_id=job.source_id,
            cost_minor=1 if kind != "change" else 0,
        )
        job.attempts.append(attempt)
        job.processing = "CORRECTING" if kind == "correction" else "QUEUED"
        job.owner = "provider"
        job.next_action = "Run reserved extraction and independent validation"
        specs.append(
            {
                "job_id": job.id,
                "source_id": job.source_id,
                "fields": fields_by_id[job.id],
                "attempt_id": attempt.id,
            }
        )
        emit(
            "correction.authorized" if kind == "correction" else "fulfillment.authorized",
            job_id=job.id,
            attempt_id=attempt.id,
            operation_id=operation_id,
        )
        emit(
            "correction.queued" if kind == "correction" else "fulfillment.queued",
            job_id=job.id,
            attempt_id=attempt.id,
            retry_from_stage="extract",
        )
    service.store.enqueue(
        db,
        operation_id,
        order.id,
        "delivery",
        {
            "kind": kind,
            "specs": specs,
            "scope_digest": scope_digest(order, now),
            "outcome": outcome,
            "change_id": change_id,
            "issue_id": issue_id,
        },
    )


def children(order, parent_jobs, fields, kind):
    result = []
    for parent in parent_jobs:
        job = Job(
            id=uid("job"),
            parent_id=parent.id,
            kind=kind,
            label=f"{parent.label}: {', '.join(fields)}",
            processing="QUEUED",
            source_id=parent.source_id,
            fields=fields,
            financial_state="PREPAID" if kind == "CHANGE_ORDER" else "NO_EXTRA_CHARGE",
        )
        order.jobs.append(job)
        result.append(job)
    return result


def amend(db, order, actor, command, now, emit):
    validate_fields(command.fields)
    if command.effective_at is None or command.effective_at.tzinfo is None:
        raise DomainError("An explicit timezone-aware effective_at is required", 422)
    when = command.effective_at.astimezone(UTC)
    if command.amendment_id:
        amendment = find(order.agreement.amendments, command.amendment_id, "Amendment")
        if amendment.fields != command.fields or amendment.effective_at != when:
            raise DomainError("Second signature must bind the exact amendment terms")
    else:
        amendment = Amendment(
            id=uid("amendment"), fields=command.fields, effective_at=when, source_id="pending"
        )
        order.agreement.amendments.append(amendment)
    attribute = f"accepted_by_{actor.role}"
    if getattr(amendment, attribute):
        raise DomainError("This party has already signed the amendment")
    other = (
        amendment.accepted_by_provider
        if actor.role == "customer"
        else amendment.accepted_by_customer
    )
    if other == actor.id:
        raise DomainError("Independent customer and provider signatures required", 403)
    setattr(amendment, attribute, actor.id)
    accepted = bool(amendment.accepted_by_customer and amendment.accepted_by_provider)
    source = store_evidence(
        db,
        order,
        canonical(amendment.model_dump(mode="json", exclude={"source_id"})).encode(),
        filename=f"{amendment.id}.json",
        media_type="application/json",
        kind="amendment",
        authority="ACCEPTED_AGREEMENT" if accepted else "PARTY_ASSERTION",
        actor_id=actor.id,
        now=now,
    )
    amendment.source_id = source.id
    if accepted:
        order.agreement.version += 1
    invalidate(order, now)
    emit(
        "agreement.accepted" if accepted else "agreement.signature_recorded",
        amendment_id=amendment.id,
        source_id=source.id,
    )


def approve(order, actor, command, now, emit):
    action = find(order.actions, command.action_id, "Action")
    if action.status != "PROPOSED":
        raise DomainError("Action is not pending approval")
    if command.verb == "decline_action":
        action.status = "DECLINED"
        if action.issue_id:
            issue = find(order.issues, action.issue_id, "Issue")
            issue.owner = "controller"
            issue.next_action = "Record a new supported decision or hand off unresolved work"
        emit("action.declined", action_id=action.id)
        return
    current_action(order, action, now)
    action.status = "APPROVED"
    action.owner = "executor"
    approval = Approval(
        id=uid("approval"),
        action_id=action.id,
        actor_id=actor.id,
        role=actor.role,
        digest=action_digest(action),
        created_at=now,
        expires_at=action.expires_at,
    )
    order.approvals.append(approval)
    if action.issue_id:
        issue = find(order.issues, action.issue_id, "Issue")
        issue.owner = "executor"
        issue.next_action = "Execute the separately approved action"
    emit("approval.recorded", action_id=action.id, approval_id=approval.id)


def execute(service, db, order, actor, command, now, emit):
    action = find(order.actions, command.action_id, "Action")
    approval = find(order.approvals, command.approval_id, "Approval")
    if (
        approval.action_id != action.id
        or approval.actor_id == actor.id
        or approval.role != "controller"
        or approval.expires_at <= now
        or approval.digest != action_digest(action)
        or action.status != "APPROVED"
    ):
        raise DomainError("An independent current approval for this exact action is required", 403)
    current_action(order, action, now)
    if action.kind == "QUOTE":
        for existing in order.change_orders:
            parents = {
                find(order.jobs, job_id, "Job").parent_id or job_id for job_id in existing.job_ids
            }
            if (
                existing.status != "DECLINED"
                and set(existing.fields).intersection(action.fields)
                and parents.intersection(action.job_ids)
            ):
                raise DomainError("An existing change order already covers these fields and units")
        change = ChangeOrder(
            id=uid("change"),
            fields=action.fields,
            job_ids=action.job_ids,
            amount_minor=action.amount_minor,
            status="DRAFT",
            action_id=action.id,
        )
        order.change_orders.append(change)
        emit("change_order.quoted", change_order_id=change.id, amount_minor=change.amount_minor)
    elif action.kind in {"INCLUDED_FIELD", "CONCESSION"}:
        if not action.issue_id:
            raise DomainError("Field fulfillment requires a targeted issue")
        issue = find(order.issues, action.issue_id, "Issue")
        if any(job.kind == "DISPUTED_FIELD" and job.issue_ids == [issue.id] for job in order.jobs):
            raise DomainError("This issue already has reserved fulfillment")
        jobs = children(order, select_jobs(order, action.job_ids), action.fields, "DISPUTED_FIELD")
        for job in jobs:
            job.issue_ids = [issue.id]
            job.dispute = "OPEN"
        queue_delivery(
            service,
            db,
            order,
            jobs,
            {job.id: action.fields for job in jobs},
            now,
            emit,
            kind="included",
            outcome=command.provider_outcome,
            issue_id=issue.id,
        )
        issue.owner = "provider"
        issue.next_action = "Fulfill the approved field obligation"
    elif action.kind == "HUMAN_REVIEW":
        issue = find(order.issues, action.issue_id, "Issue")
        issue.owner = "controller"
        issue.next_action = "Obtain accepted terms or a documented business decision"
        issue.state = "WAITING_INTERNAL"
    elif action.kind == "NO_REMEDY":
        issue = find(order.issues, action.issue_id, "Issue")
        issue.state = "RESOLVED"
        issue.resolution = action.basis
        issue.owner = "customer"
        issue.next_action = "No additional work or charge; inspect the verified delivery"
        for question in issue.questions:
            if question.status == "OPEN":
                question.status = "CANCELLED"
        for job in order.jobs:
            if issue.id in job.issue_ids:
                job.dispute = "RESOLVED"
        emit("dispute.resolved", issue_id=issue.id, action_id=action.id, no_remedy=True)
    else:
        raise DomainError("Use the bounded provider correction command")
    action.status = "EXECUTED"
    emit("action.executed", action_id=action.id)


def payment(service, db, order, command, now, emit):
    change = (
        find(order.change_orders, command.change_order_id, "Change order")
        if command.change_order_id
        else None
    )
    if change:
        if change.status != "ACCEPTED" or not change.accepted_by:
            raise DomainError("Payment requires separately accepted new scope")
        if set(change.fields).intersection(effective_fields(order, now)):
            raise DomainError(
                "New scope is now owed; obtain a revised agreement/quote before charging"
            )
    if any(op.change_order_id == command.change_order_id for op in order.finance.operations):
        raise DomainError("A payment intent already exists; reconcile or hand off, never resend")
    operation = PaymentOperation(
        id=uid("payment"),
        change_order_id=command.change_order_id,
        amount_minor=change.amount_minor
        if change
        else (order.agreement.document_count * order.agreement.unit_price_minor),
        status="PENDING",
        provider_reference="local-simulator:reserved",
    )
    order.finance.operations.append(operation)
    if change:
        change.status = "PAYMENT_PENDING"
        change.operation_id = operation.id
    service.store.enqueue(
        db,
        operation.id,
        order.id,
        "payment",
        {
            "order_id": order.id,
            "change_order_id": command.change_order_id,
            "amount_minor": operation.amount_minor,
            "outcome": command.provider_outcome,
        },
    )
    emit("payment.reserved", operation_id=operation.id, simulated=True)


def accept_delivery(service, db, order, command, now, emit):
    jobs = select_jobs(order, command.job_ids)
    for job in jobs:
        if job.kind == "CHANGE_ORDER":
            raise DomainError("Use accept_change_delivery for paid added scope")
        if job.processing != "VALIDATED" or not job.artifact_id:
            raise DomainError("Only independently validated delivery can be accepted")
        if job.dispute not in {"NONE", "RESOLVED"}:
            # Explicit acceptance of the included-field child resolves just that issue.
            if job.kind != "DISPUTED_FIELD":
                raise DomainError("Open disputes block original-unit acceptance")
        raw, _, _ = service.store.artifact(db, order.id, job.source_id)
        output, _, _ = service.store.artifact(db, order.id, job.artifact_id)
        required = effective_fields(order, now) if job.kind == "ORIGINAL" else job.fields
        if any(check.state != "PASSED" for check in verify(raw, output, job.source_id, required)):
            raise DomainError("Delivery no longer satisfies current effective scope")
        job.accepted_artifact_id = job.artifact_id
        job.obligation = "FULFILLED"
        job.owner = "customer"
        job.next_action = "Accepted; no remaining delivery action"
        if job.kind == "DISPUTED_FIELD":
            issue = find(order.issues, job.issue_ids[0], "Issue")
            peers = [
                peer
                for peer in order.jobs
                if peer.kind == "DISPUTED_FIELD" and issue.id in peer.issue_ids
            ]
            if all(peer.accepted_artifact_id for peer in peers):
                issue.state = "RESOLVED"
                issue.resolution = "Included field artifact explicitly accepted by customer"
                issue.next_action = "No remaining issue action"
                for peer in order.jobs:
                    if issue.id in peer.issue_ids:
                        peer.dispute = (
                            "RESOLVED"
                            if all(
                                find(order.issues, iid, "Issue").state == "RESOLVED"
                                for iid in peer.issue_ids
                            )
                            else "OPEN"
                        )
        emit("delivery.accepted", job_id=job.id, artifact_id=job.artifact_id)
    recognize_originals(db, order, now, emit)


def apply_command(service, db, order, actor, command, now, emit):
    verb = command.verb
    if command.provider_outcome != "SUCCESS" and (
        not service.demo
        or verb not in {"correct", "execute_action", "receive_payment", "fulfill_change"}
    ):
        raise DomainError(
            "Failure injection is restricted to controlled local simulated execution", 403
        )
    if verb == "correct":
        jobs = select_jobs(
            order,
            command.job_ids
            or [
                job.id
                for job in order.jobs
                if job.kind == "ORIGINAL" and job.processing == "FAILED" and not job.attempts
            ],
        )
        for job in jobs:
            if (
                job.kind != "ORIGINAL"
                or job.processing != "FAILED"
                or not job.recoverable
                or job.obligation != "OPEN"
            ):
                raise DomainError("Only recoverable failed original units may be corrected")
            raw, _, _ = service.store.artifact(db, order.id, job.source_id)
            output, _, _ = service.store.artifact(db, order.id, job.artifact_id)
            if all(
                check.state == "PASSED" for check in verify(raw, output, job.source_id, job.fields)
            ):
                raise DomainError("No machine-verified original-scope defect")
        queue_delivery(
            service,
            db,
            order,
            jobs,
            {job.id: effective_fields(order, now) for job in jobs},
            now,
            emit,
            kind="correction",
            outcome=command.provider_outcome,
        )
    elif verb == "accept_delivery":
        accept_delivery(service, db, order, command, now, emit)
    elif verb == "amend_agreement":
        amend(db, order, actor, command, now, emit)
    elif verb in {"approve_action", "decline_action"}:
        approve(order, actor, command, now, emit)
    elif verb == "execute_action":
        execute(service, db, order, actor, command, now, emit)
    elif verb == "open_dispute":
        jobs = select_jobs(order, command.job_ids)
        validate_fields(command.fields)
        if len(command.fields) != 1 or not command.text or len(command.text) > 20000:
            raise DomainError("Provide one disputed field and bounded complaint text", 422)
        issue = Issue(
            id=uid("issue"),
            job_ids=[job.id for job in jobs],
            field=command.fields[0],
            title=command.text[:200],
        )
        order.issues.append(issue)
        source = store_evidence(
            db,
            order,
            command.text.encode(),
            filename="complaint.txt",
            media_type="text/plain",
            kind="message",
            authority="PARTY_ASSERTION",
            actor_id=actor.id,
            now=now,
        )
        issue.messages.append(
            Message(
                id=uid("message"),
                issue_id=issue.id,
                author_id=actor.id,
                author_name=actor.name,
                text=command.text,
                timestamp=now,
                source_id=source.id,
            )
        )
        for job in jobs:
            job.issue_ids.append(issue.id)
            job.dispute = "OPEN"
        invalidate(order, now)
        emit("dispute.opened", issue_id=issue.id)
    elif verb == "answer":
        from app.runtime.jobflow_investigations import queue_investigation

        issue = find(order.issues, command.issue_id, "Issue")
        question = find(issue.questions, command.question_id, "Question")
        if question.recipient != actor.role:
            raise DomainError("Answer must come from the question's addressed role", 403)
        if question.status != "OPEN" or not command.text or len(command.text) > 20000:
            raise DomainError("Question must be open and answer must be nonempty and bounded")
        source = store_evidence(
            db,
            order,
            command.text.encode(),
            filename=f"{question.id}-answer.txt",
            media_type="text/plain",
            kind="message",
            authority="PARTY_ASSERTION",
            actor_id=actor.id,
            now=now,
        )
        message = Message(
            id=uid("message"),
            issue_id=issue.id,
            author_id=actor.id,
            author_name=actor.name,
            text=command.text,
            timestamp=now,
            source_id=source.id,
            question_id=question.id,
        )
        issue.messages.append(message)
        question.status = "ANSWERED"
        question.answer_id = message.id
        invalidate(order, now)
        emit("answer.received", question_id=question.id, issue_id=issue.id, source_id=source.id)
        # A party response resumes the exact issue, but never authorizes a paid model call.
        queue_investigation(
            service, db, order, issue.id, "DETERMINISTIC", now, emit, question_id=question.id
        )
    elif verb in {"accept_change", "decline_change"}:
        change = find(order.change_orders, command.change_order_id, "Change order")
        if change.status != "DRAFT":
            raise DomainError("Only a draft change order can be accepted or declined")
        if verb == "accept_change":
            action = find(order.actions, change.action_id, "Action")
            current_action(order, action, now)
            change.status = "ACCEPTED"
            change.accepted_by = actor.id
        else:
            change.status = "DECLINED"
        emit(
            "change_order.accepted" if verb == "accept_change" else "change_order.declined",
            change_order_id=change.id,
        )
    elif verb == "receive_payment":
        payment(service, db, order, command, now, emit)
    elif verb == "fulfill_change":
        change = find(order.change_orders, command.change_order_id, "Change order")
        if change.status != "PAID" or any(
            job.kind == "CHANGE_ORDER" and job.id in change.job_ids for job in order.jobs
        ):
            raise DomainError("Change must be paid and not already reserved for fulfillment")
        jobs = children(order, select_jobs(order, change.job_ids), change.fields, "CHANGE_ORDER")
        change.job_ids = [job.id for job in jobs]
        queue_delivery(
            service,
            db,
            order,
            jobs,
            {job.id: change.fields for job in jobs},
            now,
            emit,
            kind="change",
            outcome=command.provider_outcome,
            change_id=change.id,
        )
    elif verb == "accept_change_delivery":
        change = find(order.change_orders, command.change_order_id, "Change order")
        if change.status != "FULFILLED":
            raise DomainError("Added scope must be paid, fulfilled and validated before acceptance")
        jobs = select_jobs(order, change.job_ids)
        for job in jobs:
            if job.processing != "VALIDATED" or job.dispute not in {"NONE", "RESOLVED"}:
                raise DomainError("Unvalidated or disputed added scope cannot be recognized")
            raw, _, _ = service.store.artifact(db, order.id, job.source_id)
            output, _, _ = service.store.artifact(db, order.id, job.artifact_id)
            if any(
                check.state != "PASSED"
                for check in verify(raw, output, job.source_id, change.fields)
            ):
                raise DomainError("Added-scope artifact failed independent acceptance checks")
            job.accepted_artifact_id = job.artifact_id
            job.obligation = "FULFILLED"
            job.financial_state = "POSTED"
            job.next_action = "Accepted; no remaining delivery action"
        change.accepted_artifact_ids = list(change.artifact_ids)
        change.status = "RECOGNIZED"
        post(
            db,
            order,
            f"accept-change:{change.id}",
            change.amount_minor,
            "contract_liability",
            "revenue",
            "Customer accepted added-scope units",
            now,
            emit,
        )
        emit("change_order.delivery_accepted", change_order_id=change.id)
    elif verb == "reconcile":
        from app.runtime.jobflow_worker import reconcile

        reconcile(service, db, order, command.operation_id, now, emit)
    elif verb == "handoff":
        if not command.text or len(command.text) > 20000:
            raise DomainError("A bounded handoff reason and next action are required", 422)
        targets = (
            [find(order.issues, command.issue_id, "Issue")] if command.issue_id else order.issues
        )
        for issue in targets:
            if issue.state != "RESOLVED":
                issue.state = "WAITING_INTERNAL"
                issue.owner = "controller"
                issue.next_action = command.text
        target_ids = command.job_ids
        if command.issue_id:
            issue_jobs = set(targets[0].job_ids)
            if target_ids and not set(target_ids) <= issue_jobs:
                raise DomainError("Targeted issue handoff cannot include unrelated jobs")
            target_ids = target_ids or targets[0].job_ids
        jobs = (
            select_jobs(order, target_ids)
            if target_ids
            else [job for job in order.jobs if job.obligation == "OPEN"]
        )
        for job in jobs:
            if job.obligation != "FULFILLED":
                job.obligation = "HANDED_OFF"
                job.owner = "controller"
                job.next_action = command.text
        if not command.issue_id and not command.job_ids:
            order.status = "HANDED_OFF"
        emit("case.handed_off", reason=command.text)
