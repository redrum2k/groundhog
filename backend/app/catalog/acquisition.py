"""One allowlisted evidence-acquisition recipe; never changes source or consent rules.

All comparison arms may invoke this same capability. A stored procedural preference
can choose to invoke it; no learned recipe can declare authority or a verdict.
"""

import base64

from app.catalog.amendments import assess_amendment
from app.contracts.catalog import Amendment, Source, UploadCommand


def registered_repair(service, order):
    """Find a current, same-scope registered artifact that passes every repair check."""
    if order.order_state != "waiting_evidence" or not order.verification:
        return None
    if not any(
        a.reason_code == "REQUIRED_VALUE_UNREADABLE"
        and a.obligation_id in order.verification.material_blockers
        for a in order.verification.assessments
    ):
        return None
    request = next((r for r in reversed(order.evidence_requests) if not r.answered), None)
    if request is None or service.clock() >= request.deadline:
        return None
    target = request.target_source
    with service.repository.transaction() as db:
        candidates = [
            Source.model_validate_json(row[0])
            for row in db.execute(
                "SELECT data FROM catalog_sources WHERE source_id=? ORDER BY version",
                (target.source_id,),
            ).fetchall()
        ]
    for source in candidates:
        if (
            source.artifact.sha256 == target.artifact.sha256
            or source.corpus_id != target.corpus_id
            or source.supplier_id != target.supplier_id
            or source.edition != target.edition
            or source.effective_date != target.effective_date
            or source.authority
            not in order.snapshot.quote.specification.terms.source_policy.accepted_authority
        ):
            continue
        candidate = Amendment(
            amendment_id=f"acquisition-check-{source.artifact.sha256}",
            evidence_request_id=request.request_id,
            target_source_id=target.source_id,
            target_version=target.version,
            actor="system:registered-evidence-acquisition",
            reason="Inspect an already registered exact-edition corroborating artifact",
            relationship="replacement_page",
            artifact=source.artifact,
            submitted_at=service.clock(),
        )
        classification, _, _ = assess_amendment(
            candidate,
            target,
            service.registry,
            service.store,
            order.snapshot.quote.specification.terms,
        )
        if classification == "evidence_only":
            return source
    return None


def acquire_registered(service, order):
    """Submit through the normal request-bound upload path; ordinary jobs reverify."""
    source = registered_repair(service, order)
    if source is None:
        return order
    request = next(r for r in reversed(order.evidence_requests) if not r.answered)
    return service.upload(
        order.snapshot.order_id,
        UploadCommand(
            expected_revision=order.revision,
            expected_binding=order.binding,
            idempotency_key=f"registered-repair:{request.request_id}:{source.artifact.sha256}",
            evidence_request_id=request.request_id,
            actor="system:registered-evidence-acquisition",
            reason=(
                "Already registered same-edition evidence; "
                "mandatory classification and consent remain required"
            ),
            relationship="replacement_page",
            pdf_base64=base64.b64encode(service.store.read(source.artifact)).decode(),
        ),
    )
