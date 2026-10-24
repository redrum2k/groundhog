"""Job-level adapter to the existing order authority, in the caller's transaction."""

from datetime import timedelta

from app.contracts.api import (
    AcceptQuote,
    CreateOrder,
    Mutation,
    OpenDispute,
    PublishDelivery,
    QuoteRequest,
    ReportFailure,
    ScopeObligation,
    SubmitInvestigation,
)
from app.contracts.models import (
    AcceptedPolicy,
    Citation,
    CriterionAssessment,
    EvidencePointer,
    EvidenceReference,
    InvestigationResult,
    InvoiceCriterion,
    Money,
    OrderSnapshot,
    OrderState,
    PdfHighlight,
    Recommendation,
)
from app.orders.service import DomainError as BaseError
from app.provider.jobflow import source_values, store_evidence
from app.provider.register import publish_register, verify_register
from app.storage.jobflow import DomainError, canonical


def reference(evidence, kind, *, parents=()):
    return EvidenceReference(
        evidence_id=evidence.id,
        version=evidence.version,
        sha256=evidence.sha256,
        storage_key=f"jobflow/{evidence.id}",
        media_type=evidence.media_type,
        kind=kind,
        derived_from=tuple(
            EvidencePointer(evidence_id=p.id, version=p.version, sha256=p.sha256) for p in parents
        ),
    )


def money(amount):
    return Money(amount_minor=amount, currency="USD", decimals=2)


def current(service, db, order):
    record = service.base.repository.get(db, order.id)
    if record is None:
        raise DomainError(
            "This saved case predates the integrated base-order contract; create a new case"
        )
    return record


def transition(service, db, order, operation, model=Mutation, **fields):
    record = current(service, db, order)
    command = model(
        expected_revision=record.revision,
        expected_binding=record.binding,
        idempotency_key=f"jobflow:{order.id}:{order.revision}:{operation}:{record.revision}",
        **fields,
    )
    try:
        return service.base.mutate(order.id, operation, command, connection=db)
    except BaseError as exc:
        raise DomainError(exc.message, exc.status) from exc


def create_base(service, db, order, request, now, emit):
    sources = [item for item in order.evidence if item.kind == "source"]
    rows = []
    for source in sources:
        raw, _, _ = service.store.artifact(db, order.id, source.id)
        rows.append({"source_id": source.id, "fields": source_values(raw)})
    structured = store_evidence(
        db,
        order,
        canonical(rows).encode(),
        filename="accepted-inputs.json",
        media_type="application/json",
        kind="source",
        authority="COMPANY_RECORD",
        actor_id="source-extractor",
        now=now,
        derived_from=[source.id for source in sources],
    )
    snapshot = OrderSnapshot(
        order_id=order.id,
        snapshot_id=order.agreement.source_id,
        accepted_at=now,
        accepted_brief=(
            "Invoice register and exceptions; eight HACK.md acceptance criteria. "
            "No FX, payment-status or category inference."
        ),
        input_versions=tuple(reference(item, "accepted_input") for item in sources),
        structured_data=(reference(structured, "structured_data", parents=sources),),
        price=money(order.agreement.document_count * order.agreement.unit_price_minor),
        policy=AcceptedPolicy(
            policy_version="invoice-review-v0.2",
            additional_processing_price=(
                money(request.additional_processing_fee_minor)
                if request.additional_processing_fee_minor
                else None
            ),
        ),
    )
    service.base.create(
        CreateOrder(
            snapshot=snapshot,
            authorization_expires_at=now + timedelta(seconds=request.authorization_seconds),
            idempotency_key=f"{order.id}:create",
        ),
        connection=db,
    )
    emit("base.authorized", simulated=True)
    if any(job.processing == "FAILED" for job in order.jobs):
        transition(
            service,
            db,
            order,
            "failure",
            ReportFailure,
            error_code="EXTRACTION_FAILED",
            message="Original unit extraction requires operational retry",
        )
    else:
        publish_base(service, db, order, now, emit)
    sync_base(service, db, order, now)


def sync_base(service, db, order, now):
    record = current(service, db, order)
    if service.base._advance(record, now):
        record.revision += 1
        service.base.repository.save(db, record)
    order.base_order = service.base.view(record)
    for job in order.jobs:
        if job.kind == "ORIGINAL":
            job.financial_state = f"BASE_{record.payment_phase.upper()}"
    return record


def sync_obligations(service, db, order):
    record = current(service, db, order)
    obligations = []
    for amendment in order.agreement.amendments:
        if not (amendment.accepted_by_customer and amendment.accepted_by_provider):
            continue
        fulfilled = True
        for original in (job for job in order.jobs if job.kind == "ORIGINAL"):
            covered = set(original.fields) if original.processing == "VALIDATED" else set()
            for child in order.jobs:
                if child.parent_id == original.id and child.processing == "VALIDATED":
                    covered.update(child.fields)
            fulfilled = fulfilled and set(amendment.fields) <= covered
        obligations.append(
            ScopeObligation(
                amendment_id=amendment.id,
                effective_at=amendment.effective_at,
                fields=tuple(amendment.fields),
                fulfilled=fulfilled,
            )
        )
    if tuple(obligations) != record.scope_obligations:
        record.scope_obligations = tuple(obligations)
        record.revision += 1
        service.base.repository.save(db, record)


def publish_base(service, db, order, now, emit):
    record = current(service, db, order)
    if record.order_state == OrderState.HUMAN_REVIEW:
        return
    document, sidecar = publish_register(service.store, db, order, now)
    transition(
        service,
        db,
        order,
        "delivery",
        PublishDelivery,
        artifacts=(reference(document, "delivery_artifact"),),
        structured_data=(reference(sidecar, "structured_data", parents=(document,)),),
    )
    emit("base.delivery_published", artifact_id=document.id)
    unresolved = [issue for issue in order.issues if issue.state != "RESOLVED"]
    if unresolved:
        transition(
            service,
            db,
            order,
            "dispute",
            OpenDispute,
            complaint="; ".join(issue.title for issue in unresolved),
        )


def after_delivery(service, db, order, request, now, emit):
    sync_obligations(service, db, order)
    if request.get("kind") == "change":
        return
    original = [job for job in order.jobs if job.kind == "ORIGINAL"]
    if any(job.processing != "VALIDATED" for job in original):
        record = current(service, db, order)
        if any(job.obligation == "HANDED_OFF" for job in original):
            service.base._hold(record, "Bounded operational retry failed; human review required")
            record.revision += 1
            service.base.repository.save(db, record)
        return
    record = current(service, db, order)
    if request.get("kind") == "included" and any(
        job.kind == "DISPUTED_FIELD" and job.processing == "FAILED" for job in order.jobs
    ):
        service.base._hold(record, "Free field regeneration failed; human review required")
        record.revision += 1
        service.base.repository.save(db, record)
        return
    if any(not item.fulfilled and item.effective_at <= now for item in record.scope_obligations):
        return
    if any(job.kind == "DISPUTED_FIELD" and job.processing != "VALIDATED" for job in order.jobs):
        return
    if (
        not record.deliveries
        or record.regeneration_pending
        or record.order_state == OrderState.FAILED
    ):
        publish_base(service, db, order, now, emit)


def verify_base(service, db, order, now, emit):
    record = current(service, db, order)
    if any(issue.state != "RESOLVED" for issue in order.issues):
        raise DomainError("Unresolved scope disputes block a compliant base verdict")
    if not record.deliveries:
        raise DomainError("Evidence review requires the actual delivered register PDF")
    parsed = verify_register(service.store, db, order, record, now)
    pdf = record.deliveries[-1].artifacts[0]
    highlights = []
    for page in parsed["pages"]:
        for word in page["words"]:
            x0, y0, x1, y1 = word["rectangle"]
            highlights.append(PdfHighlight(page_number=page["page"], x0=x0, y0=y0, x1=x1, y1=y1))
    citation = Citation(
        evidence_id=pdf.evidence_id,
        version=pdf.version,
        sha256=pdf.sha256,
        locator="Verified register rows, source links, exceptions and totals",
        highlights=tuple(highlights),
    )
    source_citations = tuple(
        Citation(
            evidence_id=item.evidence_id,
            version=item.version,
            sha256=item.sha256,
            locator="Accepted source extraction, independently reopened against each PDF",
        )
        for item in record.snapshot.structured_data
    )
    result = InvestigationResult(
        case_id=record.case_id,
        proposal=record.binding,
        findings=(),
        unresolved_issues=(),
        verdict="compliant",
        claim_assessment="refuted" if record.complaint else "not_applicable",
        checks=tuple(
            CriterionAssessment(
                criterion=criterion,
                status="passed",
                explanation=(
                    "Reopened source PDFs and unit artifacts; checked grouped IDs/conflicts, "
                    "amounts, totals, references and exact final PDF lines."
                ),
                citations=(citation, *source_citations),
            )
            for criterion in InvoiceCriterion
        ),
        questions=(),
        recommendations=(
            Recommendation(
                action="capture", rationale="Eight source-backed register checks passed"
            ),
        ),
    )
    transition(service, db, order, "investigation", SubmitInvestigation, result=result)
    emit("base.verdict_recorded", verdict="compliant", simulated=True)


def before_command(service, db, order, command, now):
    record = current(service, db, order)
    if (
        command.verb in {"correct", "verify_base", "accept_base", "answer"}
        and record.order_state == OrderState.HUMAN_REVIEW
    ):
        raise DomainError("Base order requires human review; no automatic payment or retry")
    if command.verb == "open_dispute" and record.deliveries:
        transition(
            service, db, order, "dispute", OpenDispute, complaint=command.text or "Scope dispute"
        )
    if (
        command.verb == "answer"
        and record.review_deadline is not None
        and now >= record.review_deadline
    ):
        raise DomainError("The ten-minute dispute review has expired")


def after_command(service, db, order, command, now, emit):
    sync_obligations(service, db, order)
    if command.verb == "verify_base":
        verify_base(service, db, order, now, emit)
    elif command.verb == "accept_base":
        if any(issue.state != "RESOLVED" for issue in order.issues):
            raise DomainError("Unresolved job disputes block base acceptance")
        transition(service, db, order, "accept")
        emit("base.accepted", simulated=True)
    elif command.verb == "quote_processing":
        if not command.amount_minor:
            raise DomainError("Controller must supply an explicit positive processing quote")
        base = current(service, db, order)
        transition(
            service,
            db,
            order,
            "quote",
            QuoteRequest,
            amount=money(command.amount_minor),
            expires_at=min(now + timedelta(minutes=10), base.authorization_expires_at),
        )
        emit("base.processing_quoted", amount_minor=command.amount_minor)
    elif command.verb == "accept_processing_quote":
        if not command.processing_quote_id:
            raise DomainError("Accept the exact displayed processing quote")
        transition(
            service, db, order, "accept_quote", AcceptQuote, quote_id=command.processing_quote_id
        )
        emit("base.processing_quote_authorized", simulated=True)
    sync_base(service, db, order, now)
