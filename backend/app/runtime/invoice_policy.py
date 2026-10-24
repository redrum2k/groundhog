"""Preserved invoice jobflow policy; catalog execution uses catalog_policy instead."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime

from app.contracts.models import (
    CaseState,
    Contract,
    DeliveryState,
    DeliveryVersion,
    InvestigationResult,
    Money,
    OrderSnapshot,
    OrderState,
    PaymentState,
    ProposalBinding,
    SettlementIntent,
    Text,
)


class CaptureContext(Contract):
    """Application facts plus a validated current verdict, never raw client authority."""

    current_proposal: ProposalBinding
    order_state: OrderState
    delivery_state: DeliveryState
    case_state: CaseState
    payment_state: PaymentState
    verification_binding: ProposalBinding | None
    customer_acceptance: ProposalBinding | None
    authorization_id: Text
    authorized_amount: Money
    authorization_expires_at: AwareDatetime
    evidence_verdict: Literal["compliant", "provider_defect", "insufficient_evidence"] | None = None


def validate_capture(
    snapshot: OrderSnapshot,
    delivery: DeliveryVersion,
    intent: SettlementIntent,
    context: CaptureContext,
    *,
    now: datetime,
    simulation: bool = False,
) -> None:
    """Fail closed. Caller must read facts/check/reserve intent in one DB transaction."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    binding = context.current_proposal
    if (
        binding.order_id != snapshot.order_id
        or binding.snapshot_id != snapshot.snapshot_id
        or delivery.order_id != snapshot.order_id
        or delivery.snapshot_id != snapshot.snapshot_id
        or binding.delivery_version != delivery.version
        or intent.proposal != binding
    ):
        raise ValueError("stale or unrelated settlement proposal")
    if intent.action != "capture":
        raise ValueError("capture guard only authorizes capture")
    if context.order_state != OrderState.DELIVERED:
        raise ValueError("order must be delivered and outside human review")
    if context.delivery_state == DeliveryState.OPERATIONAL_FAILURE:
        raise ValueError("operational failure cannot be captured")
    if context.evidence_verdict == "provider_defect":
        raise ValueError("known provider defect must be remedied")
    if context.verification_binding is not None and context.verification_binding != binding:
        raise ValueError("stale evidence verdict")
    if context.case_state not in (CaseState.NONE, CaseState.RESOLVED):
        raise ValueError("open disputes and human review block automatic capture")
    if context.payment_state != PaymentState.AUTHORIZED and not (
        simulation and context.payment_state == PaymentState.MOCK
    ):
        raise ValueError("capture requires authorization; reconcile submitted/uncertain operations")
    if intent.authorization_id != context.authorization_id:
        raise ValueError("authorization does not match")
    authorized = context.authorized_amount
    if (
        intent.amount != snapshot.price
        or authorized.currency != snapshot.price.currency
        or authorized.decimals != snapshot.price.decimals
        or authorized.amount_minor < snapshot.price.amount_minor
    ):
        raise ValueError("capture must equal the accepted price within the authorized amount")
    if now >= context.authorization_expires_at:
        raise ValueError("payment authorization has expired independently of customer review")
    if delivery.delivered_at < snapshot.accepted_at or now < delivery.delivered_at:
        raise ValueError("invalid delivery timing")
    if context.customer_acceptance is not None and context.customer_acceptance != binding:
        raise ValueError("stale customer acceptance")
    review_deadline = delivery.delivered_at + timedelta(
        seconds=snapshot.policy.review_window_seconds
    )
    evidenced = context.evidence_verdict == "compliant" and context.verification_binding == binding
    if context.customer_acceptance is None and not evidenced and now < review_deadline:
        raise ValueError("evidence verdict, customer acceptance or review expiry is required")


def validate_additional_processing(
    snapshot: OrderSnapshot,
    intent: SettlementIntent,
    result: InvestigationResult,
    current_binding: ProposalBinding,
    *,
    approved_quote: Money | None = None,
) -> None:
    if intent.action != "additional_processing" or intent.proposal != current_binding:
        raise ValueError("additional processing requires the current proposal")
    if (
        result.proposal != current_binding
        or result.verdict != "compliant"
        or result.claim_assessment != "refuted"
    ):
        raise ValueError("additional processing requires an evidence-backed refutation")
    agreed = snapshot.policy.additional_processing_price or approved_quote
    if agreed is None or intent.amount != agreed:
        raise ValueError("additional processing requires the agreed fee or an accepted quote")
    if (agreed.currency, agreed.decimals) != (snapshot.price.currency, snapshot.price.decimals):
        raise ValueError("additional processing must use the accepted currency and precision")


def decide_remedy(
    assessment: Literal["provider_defect", "unsupported", "ambiguous"],
    free_regenerations_used: int,
    *,
    regeneration_failed: bool = False,
    questions_asked: int = 0,
) -> Literal["free_regeneration", "human_review", "additional_processing", "request_evidence"]:
    """Evidence-backed agent verdicts drive remedies within the accepted policy."""
    if type(free_regenerations_used) is not int or free_regenerations_used not in (0, 1):
        raise ValueError("at most one free regeneration is permitted")
    if assessment not in ("provider_defect", "unsupported", "ambiguous"):
        raise ValueError("unknown assessment")
    if type(questions_asked) is not int or questions_asked not in (0, 1, 2):
        raise ValueError("at most two questions are permitted")
    if regeneration_failed:
        return "human_review"
    if assessment == "ambiguous":
        return "human_review" if questions_asked == 2 else "request_evidence"
    if assessment == "provider_defect":
        return "human_review" if free_regenerations_used == 1 else "free_regeneration"
    return "additional_processing"
