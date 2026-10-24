"""Commercial authority is deterministic and independent of semantic scores."""

from app.catalog.verification import material_blockers


def authorization_ready(authorization):
    receipt = authorization.receipt
    if receipt is None:
        return False
    return (
        authorization.status == "mock_authorized"
        and receipt.mode == "mock"
        and receipt.status == "mock"
    ) or (
        authorization.status == "authorized"
        and receipt.mode == "live"
        and receipt.status == "confirmed"
    )


def capture_allowed(order, now):
    report = order.verification
    if order.order_state != "delivered" or not order.deliveries or order.authority_state != "clear":
        return False
    if any(c.status in ("open", "human_review", "scope_change") for c in order.cases):
        return False
    if (
        report is None
        or report.binding != order.binding
        or report.stage not in ("delivery", "dispute")
    ):
        return False
    if (
        not report.passed
        or report.provider_defect
        or material_blockers(report.obligations, report.assessments)
    ):
        return False
    if any(
        o.mandatory and a.result != "PASS"
        for o, a in zip(report.obligations, report.assessments, strict=True)
    ):
        return False
    mandatory = {o.obligation_id for o in report.obligations if o.mandatory}
    required = {"global:pdf", "global:fields", "global:completeness", "global:provenance"}
    required.update(f"{s.source_id}:index" for s in order.sources)
    if not required.issubset(mandatory):
        return False
    if not authorization_ready(order.authorization) or now >= order.authorization.expires_at:
        return False
    if order.authorization.amount != order.snapshot.quote.amount or any(
        b.kind == "capture" for b in order.ledger
    ):
        return False
    current = order.deliveries[-1]
    return order.customer_acceptance == order.binding or now >= current.review_deadline
