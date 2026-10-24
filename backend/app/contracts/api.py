"""Historical v0.2 JSON decoding only. No v0.2 mutation routes are mounted."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt

from app.contracts.models import (
    CaseState,
    Contract,
    CustomerAnswer,
    DeliveryState,
    DeliveryVersion,
    EvidenceReference,
    InvestigationQuestion,
    InvestigationResult,
    Money,
    OrderSnapshot,
    OrderState,
    PaymentState,
    ProposalBinding,
    Text,
    Version,
)
from app.payments.interfaces import PaymentReceipt


class CreateOrder(Contract):
    snapshot: OrderSnapshot
    authorization_expires_at: AwareDatetime
    idempotency_key: Text


class Mutation(Contract):
    expected_revision: Version
    expected_binding: ProposalBinding | None
    idempotency_key: Text


class PublishDelivery(Mutation):
    artifacts: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    structured_data: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]


class ReportFailure(Mutation):
    error_code: Text
    message: Text


class OpenDispute(Mutation):
    complaint: Text
    refund_requested: bool = False


class SubmitAnswer(Mutation):
    question_id: Text
    text: Text


class SubmitInvestigation(Mutation):
    result: InvestigationResult


class QuoteRequest(Mutation):
    amount: Money
    expires_at: AwareDatetime


class AcceptQuote(Mutation):
    quote_id: Text


class ProcessingQuote(Contract):
    quote_id: Text
    amount: Money
    expires_at: AwareDatetime
    binding: ProposalBinding


class LedgerEntry(Contract):
    entry_id: Text
    kind: Literal["base", "additional_processing"]
    amount: Money
    recorded_at: AwareDatetime
    reason: Literal["evidence_verdict", "customer_acceptance", "review_cutoff", "accepted_quote"]
    receipt: PaymentReceipt


class OrderRecord(BaseModel):
    """Mutable only inside the repository's serialized transaction."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    snapshot: OrderSnapshot
    revision: Version = 1
    order_state: OrderState = OrderState.PROCESSING
    delivery_state: DeliveryState = DeliveryState.PENDING_VERIFICATION
    case_state: CaseState = CaseState.NONE
    payment_state: PaymentState = PaymentState.MOCK
    payment_phase: Literal["open", "held", "booked", "expired"] = "open"
    authorization_id: Text
    authorization_expires_at: AwareDatetime
    authorization_receipt: PaymentReceipt
    deliveries: tuple[DeliveryVersion, ...] = ()
    binding: ProposalBinding | None = None
    evidence: tuple[EvidenceReference, ...]
    review_deadline: AwareDatetime | None = None
    case_id: Text | None = None
    complaint: Text | None = None
    refund_requested: bool = False
    questions: tuple[InvestigationQuestion, ...] = ()
    answers: tuple[CustomerAnswer, ...] = ()
    questions_asked: Annotated[StrictInt, Field(ge=0, le=2)] = 0
    free_regenerations_used: Annotated[StrictInt, Field(ge=0, le=1)] = 0
    regeneration_pending: bool = False
    result: InvestigationResult | None = None
    failure: Text | None = None
    requires_quote: bool = False
    quote: ProcessingQuote | None = None
    ledger: tuple[LedgerEntry, ...] = ()


class OrderView(Contract):
    order: OrderRecord
    server_time: AwareDatetime
    poll_after_ms: Literal[2000] = 2000
    available_actions: tuple[str, ...]
    display_status: Literal[
        "processing", "correct", "needs_review", "operational_failure", "human_review"
    ]
