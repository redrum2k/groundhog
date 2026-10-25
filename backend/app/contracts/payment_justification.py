"""Read-only explanation of persisted facts, never a payment capability."""

from typing import Literal

from pydantic import AwareDatetime

from app.contracts.catalog import (
    Assessment,
    Authorization,
    Binding,
    Booking,
    Case,
    ReviewerDecision,
    Snapshot,
)
from app.contracts.models import Contract
from app.contracts.payments import PaymentView


class PaymentJustification(Contract):
    kind: Literal["payment_justification_v1"] = "payment_justification_v1"
    observed_at: AwareDatetime
    order_id: str
    revision: int
    binding: Binding
    agreement: Snapshot
    exact_price: str
    amount_atomic: str | None
    state: str
    capture_eligible_now: bool
    blockers: tuple[str, ...]
    bytes_revalidated: bool
    checks: tuple[Assessment, ...]
    source_hashes: dict[str, str]
    delivery_hashes: dict[str, str]
    authorization: Authorization
    customer_acceptance: Binding | None
    review_deadline: AwareDatetime | None
    latest_safe_capture_at: AwareDatetime
    cases: tuple[Case, ...]
    decisions: tuple[ReviewerDecision, ...]
    bookings: tuple[Booking, ...]
    payment: PaymentView | None
    limitations: tuple[str, ...] = (
        "Read-only observation, not approval or a reusable payment capability. "
        "Gates are rechecked at execution.",
        "Bookings and operations are original persisted records, "
        "not reconstructed receipts or a general ledger.",
        "Current eligibility is not a replay of historical eligibility; "
        "terminal receipts describe prior outcomes.",
        "Mock settlement is not an on-chain transaction. "
        "Evidence judgments do not authorize money movement.",
    )
