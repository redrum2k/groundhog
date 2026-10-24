from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime

from app.contracts.models import (
    CaseState,
    Contract,
    DeliveryState,
    DeliveryVersion,
    Money,
    OrderSnapshot,
    OrderState,
    PaymentState,
    ProposalBinding,
    SettlementIntent,
    Text,
)


class CaptureContext(Contract):
    """Trusted application facts, never constructed from an investigator's output."""

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


def validate_capture(
    snapshot: OrderSnapshot,
    delivery: DeliveryVersion,
    intent: SettlementIntent,
    context: CaptureContext,
    *,
    now: datetime,
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
    if context.delivery_state != DeliveryState.PASSED or context.verification_binding != binding:
        raise ValueError("current delivery and evidence must pass verification")
    if context.case_state not in (CaseState.NONE, CaseState.RESOLVED):
        raise ValueError("open disputes and human review block automatic capture")
    if context.payment_state != PaymentState.AUTHORIZED:
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
    if context.customer_acceptance is None and now < review_deadline:
        raise ValueError("customer acceptance or review expiry is required")


def decide_remedy(
    assessment: Literal["provider_defect", "unsupported", "ambiguous"],
    free_regenerations_used: int,
    *,
    regeneration_failed: bool = False,
) -> Literal["free_regeneration", "human_review", "no_remedy"]:
    """Application-verified assessment, not an agent's recommendation or payment permission."""
    if type(free_regenerations_used) is not int or free_regenerations_used not in (0, 1):
        raise ValueError("at most one free regeneration is permitted")
    if assessment not in ("provider_defect", "unsupported", "ambiguous"):
        raise ValueError("unknown assessment")
    if regeneration_failed or assessment == "ambiguous":
        return "human_review"
    if assessment == "provider_defect":
        return "human_review" if free_regenerations_used == 1 else "free_regeneration"
    return "no_remedy"
