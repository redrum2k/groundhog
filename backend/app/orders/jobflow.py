"""Synthetic intake creates real source/output bytes and explicit historical acceptance."""

import json

from app.contracts.jobflow import Agreement, Issue, Job, Message, OrderView, PaymentOperation
from app.payments.jobflow import post, project
from app.provider.jobflow import (
    BASE_FIELDS,
    cite,
    extract,
    invoice,
    parse_pdf,
    store_evidence,
    validate_fields,
    verify,
)
from app.runtime.jobflow_policy import proposal
from app.storage.jobflow import DomainError, canonical, uid


def prepare_intake(request):
    validate_fields(request.agreement_fields)
    validate_fields(request.requested_fields, allow_empty=True)
    if request.disputed_field:
        validate_fields([request.disputed_field])
    if not set(BASE_FIELDS) <= set(request.agreement_fields):
        raise DomainError("Synthetic intake requires the four base invoice fields", 422)
    records = []
    for index in range(1, request.document_count + 1):
        source_id = uid("invoice")
        raw = invoice(index)
        output = extract(raw, source_id, request.agreement_fields)
        historical = index <= request.document_count - request.failed_count
        if not historical:
            value = json.loads(output)
            value["fields"].pop("amount")
            output = canonical(value).encode()
        records.append(
            (
                source_id,
                raw,
                parse_pdf(raw),
                output,
                verify(raw, output, source_id, request.agreement_fields),
                historical,
            )
        )
    return records


def create_order(db, store, actor, request, records, now, model_available):
    order_id = uid("order")
    agreement_id = uid("agreement")
    order = OrderView(
        id=order_id,
        case_id=uid("case"),
        revision=1,
        customer_id=actor.customer_id or "northwind",
        customer_name=request.customer_name,
        title=request.title,
        created_at=now,
        model_available=model_available,
        agreement=Agreement(
            fields=request.agreement_fields,
            unit_price_minor=request.unit_price_minor,
            document_count=request.document_count,
            source_id=agreement_id,
        ),
        jobs=[],
        evidence=[],
    )

    def emit(kind, **payload):
        store.event(db, order, actor.id, request.idempotency_key, now, kind, **payload)

    store_evidence(
        db,
        order,
        canonical(order.agreement.model_dump(mode="json")).encode(),
        filename="accepted-agreement.json",
        media_type="application/json",
        kind="agreement",
        authority="ACCEPTED_AGREEMENT",
        actor_id="synthetic-company",
        now=now,
        source_id=agreement_id,
    )
    emit("order.created", synthetic=True, policy_id=order.agreement.policy_id)
    accepted_ids = []
    for index, (source_id, raw, parsed, output, checks, historical) in enumerate(records, 1):
        source = store_evidence(
            db,
            order,
            raw,
            filename=f"invoice-{index:04d}.pdf",
            media_type="application/pdf",
            kind="source",
            authority="COMPANY_RECORD",
            actor_id="synthetic-company",
            now=now,
            source_id=source_id,
            extraction=parsed,
        )
        artifact = store_evidence(
            db,
            order,
            output,
            filename=f"extraction-{index:04d}.json",
            media_type="application/json",
            kind="artifact",
            authority="COMPANY_RECORD",
            actor_id="synthetic-provider",
            now=now,
            derived_from=[source.id],
        )
        for check in checks:
            check.citations = [cite(source), cite(artifact)]
        job = Job(
            id=uid("job"),
            label=f"Invoice {index:03d}",
            original_index=index,
            processing="VALIDATED" if historical else "FAILED",
            source_id=source.id,
            artifact_id=artifact.id,
            accepted_artifact_id=artifact.id if historical else None,
            fields=request.agreement_fields,
            checks=checks,
            obligation="FULFILLED" if historical else "OPEN",
            financial_state="ACCEPTED_UNFUNDED" if historical else "PREPAID",
            next_action="Historical acceptance recorded"
            if historical
            else "Correct missing amount",
            owner="customer" if historical else "provider",
        )
        order.jobs.append(job)
        if historical:
            accepted_ids.append(job.id)
        emit("job.created", job_id=job.id, source_id=source.id, artifact_id=artifact.id)
        emit("check.passed" if historical else "check.failed", job_id=job.id)
    store_evidence(
        db,
        order,
        canonical(
            {
                "synthetic": True,
                "accepted_job_ids": accepted_ids,
                "basis": "Fictional initial customer acceptance record",
            }
        ).encode(),
        filename="historical-acceptance.json",
        media_type="application/json",
        kind="verification",
        authority="COMPANY_RECORD",
        actor_id="synthetic-company",
        now=now,
    )
    if request.initial_receipt != "NONE":
        operation = PaymentOperation(
            id=uid("payment"),
            amount_minor=request.document_count * request.unit_price_minor,
            status=request.initial_receipt,
            provider_reference="local-simulator:initial-prepayment",
        )
        order.finance.operations.append(operation)
        db.execute(
            "INSERT INTO jf_provider_results VALUES(?,?)",
            (
                operation.id,
                canonical(
                    {
                        "status": "CONFIRMED",
                        "amount_minor": operation.amount_minor,
                        "order_id": order.id,
                        "change_order_id": None,
                    }
                ),
            ),
        )
        if operation.status == "CONFIRMED":
            post(
                db,
                order,
                f"receipt:{operation.id}",
                operation.amount_minor,
                "cash",
                "contract_liability",
                "Simulated original prepayment",
                now,
                emit,
            )
            recognize_originals(db, order, now, emit)
        emit(
            "payment.confirmed" if operation.status == "CONFIRMED" else "payment.unknown",
            operation_id=operation.id,
            simulated=True,
        )
    if request.disputed_field:
        job = next((job for job in order.jobs if job.processing == "VALIDATED"), order.jobs[0])
        issue = Issue(
            id=uid("issue"),
            job_ids=[job.id],
            field=request.disputed_field,
            title=f"Is {request.disputed_field} included?",
        )
        order.issues.append(issue)
        complaint = (
            f"At kickoff we discussed {request.disputed_field}. I understood that it was "
            "included in the accepted work. Please check the agreement and our messages."
        )
        message_source = store_evidence(
            db,
            order,
            complaint.encode(),
            filename="customer-kickoff-message.txt",
            media_type="text/plain",
            kind="message",
            authority="PARTY_ASSERTION",
            actor_id="customer",
            now=now,
        )
        issue.messages.append(
            Message(
                id=uid("message"),
                issue_id=issue.id,
                author_id="customer",
                author_name=request.customer_name,
                text=complaint,
                timestamp=now,
                source_id=message_source.id,
            )
        )
        job.issue_ids.append(issue.id)
        job.dispute = "OPEN"
        emit("dispute.opened", issue_id=issue.id, job_id=job.id)
    fields = [field for field in request.requested_fields if field not in request.agreement_fields]
    if fields:
        order.actions.append(
            proposal(
                order,
                now,
                kind="QUOTE",
                fields=fields,
                job_ids=[job.id for job in order.jobs],
                basis="Separate additional scope at two cents per field per document",
                citations=[cite(order.evidence[0])],
            )
        )
        emit("action.proposed", action_id=order.actions[-1].id)
    project(db, order, now)
    return order


def recognize_originals(db, order, now, emit):
    if not any(
        op.change_order_id is None and op.status == "CONFIRMED" for op in order.finance.operations
    ):
        return
    for job in order.jobs:
        if job.kind == "ORIGINAL" and job.accepted_artifact_id:
            post(
                db,
                order,
                f"accept:{order.id}:{job.id}",
                order.agreement.unit_price_minor,
                "contract_liability",
                "revenue",
                "Accepted original unit",
                now,
                emit,
            )
            job.financial_state = "POSTED"
