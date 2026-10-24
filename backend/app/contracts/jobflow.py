"""Canonical, additive contract for the seller's unit-priced job workflow."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.contracts.api import OrderView as BaseOrderView
from app.contracts.api import QuoteAuthorization

Identifier = Annotated[str, Field(min_length=1, max_length=160)]
Cents = Annotated[StrictInt, Field(ge=0)]
Revision = Annotated[StrictInt, Field(ge=1)]
Role = Literal["customer", "provider", "investigator", "controller", "executor"]
Mode = Literal["SIMULATED", "LIVE", "READ_ONLY_REPLAY"]
Processing = Literal["QUEUED", "RUNNING", "FAILED", "CORRECTING", "VALIDATED", "CANCELLED"]
Dispute = Literal[
    "NONE", "OPEN", "INVESTIGATING", "WAITING_CUSTOMER", "WAITING_INTERNAL", "RESOLVED"
]
Obligation = Literal["OPEN", "FULFILLED", "CANCELLED_WITH_AUTHORITY", "HANDED_OFF"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Actor(Model):
    id: Identifier
    name: str
    role: Role
    customer_id: str | None = None


class Mutation(Model):
    idempotency_key: Identifier
    expected_revision: Revision


class SourceLocation(Model):
    source_id: Identifier
    version: Revision
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    quote: str
    locator: str
    page: int | None = None
    rectangle: tuple[float, float, float, float] | None = None


class Evidence(Model):
    id: Identifier
    version: Revision = 1
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    filename: str
    media_type: str
    kind: Literal["agreement", "amendment", "message", "source", "artifact", "verification"]
    authority: Literal["COMPANY_RECORD", "ACCEPTED_AGREEMENT", "PARTY_ASSERTION"]
    text: str
    created_at: datetime
    origin_actor_id: str
    derived_from: list[str] = Field(default_factory=list)


class Agreement(Model):
    version: Revision = 1
    fields: list[str]
    unit_price_minor: Cents = 100
    additional_field_price_minor: Cents = 2
    currency: Literal["USD_SIM"] = "USD_SIM"
    decimals: Literal[2] = 2
    document_count: Annotated[StrictInt, Field(ge=1, le=1000)]
    correction_attempt_limit: Literal[1] = 1
    correction_unit_cost_minor: Cents = 1
    correction_budget_minor: Cents = 100
    policy_id: Literal["invoice-review-v0.2"] = "invoice-review-v0.2"
    source_id: str
    amendments: list["Amendment"] = Field(default_factory=list)


class Amendment(Model):
    id: Identifier
    fields: list[str]
    effective_at: AwareDatetime
    accepted_by_customer: str | None = None
    accepted_by_provider: str | None = None
    source_id: str


class Check(Model):
    id: Identifier
    label: str
    state: Literal["PASSED", "FAILED", "PENDING", "DISPUTED"]
    detail: str
    citations: list[SourceLocation] = Field(default_factory=list)


class Attempt(Model):
    id: Identifier
    operation_id: Identifier
    number: Revision
    status: Literal["QUEUED", "RUNNING", "VALIDATED", "FAILED", "UNKNOWN"]
    retry_from_stage: Literal["extract", "validate"] = "extract"
    input_artifact_id: str
    output_artifact_id: str | None = None
    cost_minor: Cents = 0
    error: str | None = None


class Job(Model):
    id: Identifier
    parent_id: str | None = None
    kind: Literal["ORIGINAL", "CORRECTION", "CHANGE_ORDER", "DISPUTED_FIELD"] = "ORIGINAL"
    label: str
    original_index: int | None = None
    processing: Processing
    dispute: Dispute = "NONE"
    obligation: Obligation = "OPEN"
    financial_state: str = "PREPAID"
    source_id: str
    artifact_id: str | None = None
    accepted_artifact_id: str | None = None
    fields: list[str]
    checks: list[Check] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    owner: str = "provider"
    next_action: str = "Validate delivery"
    recoverable: bool = True


class Message(Model):
    id: Identifier
    issue_id: Identifier
    author_id: str
    author_name: str
    text: str
    timestamp: datetime
    source_id: str | None = None
    question_id: str | None = None


class Question(Model):
    id: Identifier
    issue_id: Identifier
    text: str = Field(min_length=1, max_length=600)
    recipient: Literal["customer", "controller"]
    status: Literal["OPEN", "ANSWERED", "CANCELLED"] = "OPEN"
    answer_id: str | None = None
    predicate: str | None = Field(default=None, max_length=160)
    agreement_version: Revision | None = None
    evidence_digest: str | None = None
    origin: Literal["DETERMINISTIC", "ANTHROPIC", "FALLBACK"] = "DETERMINISTIC"


class Finding(Model):
    id: Identifier
    issue_id: Identifier
    statement: str
    status: Literal["SUPPORTED", "CONTRADICTED", "CONFLICTING", "INSUFFICIENT"]
    citations: list[SourceLocation] = Field(default_factory=list)


class Issue(Model):
    id: Identifier
    job_ids: list[str]
    field: str
    title: str
    state: Dispute = "OPEN"
    owner: str = "investigator"
    next_action: str = "Inspect accepted scope and communications"
    findings: list[Finding] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    resolution: str | None = None


class Action(Model):
    id: Identifier
    kind: Literal["CORRECT", "QUOTE", "INCLUDED_FIELD", "CONCESSION", "HUMAN_REVIEW", "NO_REMEDY"]
    issue_id: str | None = None
    job_ids: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    amount_minor: Cents = 0
    basis: str
    citations: list[SourceLocation] = Field(default_factory=list)
    revision: Revision
    agreement_version: Revision
    evidence_digest: str
    scope_digest: str
    expires_at: datetime
    status: Literal["PROPOSED", "APPROVED", "DECLINED", "EXECUTED", "STALE"] = "PROPOSED"
    owner: str


class Approval(Model):
    id: Identifier
    action_id: Identifier
    actor_id: Identifier
    role: Role
    digest: str
    created_at: datetime
    expires_at: datetime


class ChangeOrder(Model):
    id: Identifier
    fields: list[str]
    job_ids: list[str]
    amount_minor: Cents
    status: Literal[
        "DRAFT",
        "ACCEPTED",
        "DECLINED",
        "PAYMENT_PENDING",
        "PAID",
        "FULFILLED",
        "RECOGNIZED",
        "UNKNOWN",
    ]
    action_id: str
    accepted_by: str | None = None
    operation_id: str | None = None
    payment_authorization: QuoteAuthorization | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    accepted_artifact_ids: list[str] = Field(default_factory=list)


class PostingLine(Model):
    account: Literal[
        "cash", "contract_liability", "revenue", "correction_expense", "compute_payable"
    ]
    debit_minor: Cents = 0
    credit_minor: Cents = 0


class Posting(Model):
    id: Identifier
    business_event_id: Identifier
    description: str
    timestamp: datetime
    lines: list[PostingLine]
    mode: Mode = "SIMULATED"

    @model_validator(mode="after")
    def balanced(self):
        if not self.lines or sum(x.debit_minor for x in self.lines) != sum(
            x.credit_minor for x in self.lines
        ):
            raise ValueError("posting must balance")
        if any(bool(x.debit_minor) == bool(x.credit_minor) for x in self.lines):
            raise ValueError("each posting line must contain one nonzero side")
        return self


class PaymentOperation(Model):
    id: Identifier
    change_order_id: str | None = None
    amount_minor: Cents
    status: Literal["PENDING", "CONFIRMED", "UNKNOWN", "FAILED"]
    provider_reference: str
    mode: Literal["SIMULATED"] = "SIMULATED"


class Finance(Model):
    currency: Literal["USD_SIM"] = "USD_SIM"
    decimals: Literal[2] = 2
    received_minor: Cents = 0
    recognized_minor: Cents = 0
    liability_minor: Cents = 0
    correction_cost_minor: Cents = 0
    approved_additions_minor: Cents = 0
    unknown_minor: Cents = 0
    postings: list[Posting] = Field(default_factory=list)
    operations: list[PaymentOperation] = Field(default_factory=list)


class Event(Model):
    id: Identifier
    sequence: Revision
    schema_version: Literal[1] = 1
    order_id: Identifier
    case_id: Identifier
    job_id: str | None = None
    attempt_id: str | None = None
    causal_id: Identifier
    timestamp: datetime
    actor_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    mode: Mode = "SIMULATED"


class InvestigationRun(Model):
    id: Identifier
    issue_id: Identifier
    revision: Revision
    status: Literal["QUEUED", "RUNNING", "COMPLETE", "FAILED", "STALE", "BLOCKED"]
    mode: Literal["DETERMINISTIC", "ANTHROPIC"]
    error: str | None = None
    elapsed_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class OrderView(Model):
    id: Identifier
    case_id: Identifier
    revision: Revision
    last_event_sequence: int = 0
    customer_id: str
    customer_name: str
    title: str
    created_at: datetime
    agreement: Agreement
    jobs: list[Job]
    evidence: list[Evidence]
    issues: list[Issue] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    change_orders: list[ChangeOrder] = Field(default_factory=list)
    finance: Finance = Field(default_factory=Finance)
    investigations: list[InvestigationRun] = Field(default_factory=list)
    status: Literal["ACTIVE", "WAITING", "COMPLETE", "HANDED_OFF"] = "ACTIVE"
    mode: Literal["SIMULATED"] = "SIMULATED"
    model_available: bool = False
    base_order: BaseOrderView | None = None


class OrderCreate(Model):
    idempotency_key: Identifier
    customer_name: Annotated[str, Field(min_length=1, max_length=120)] = "Northwind"
    title: str = "October document extraction"
    document_count: Annotated[StrictInt, Field(ge=1, le=1000)] = 100
    failed_count: Annotated[StrictInt, Field(ge=0, le=1000)] = 20
    disputed_field: str | None = "due_date"
    requested_fields: list[str] = Field(
        default_factory=lambda: ["purchase_order", "cost_center", "tax_id", "payment_terms"]
    )
    agreement_fields: list[str] = Field(
        default_factory=lambda: ["invoice_number", "vendor", "amount", "currency"]
    )
    unit_price_minor: Annotated[StrictInt, Field(ge=1, le=100000)] = 100
    initial_receipt: Literal["CONFIRMED", "UNKNOWN", "NONE"] = "CONFIRMED"
    authorization_seconds: Annotated[StrictInt, Field(ge=1, le=86400)] = 3600
    additional_processing_fee_minor: Cents = 0

    @model_validator(mode="after")
    def counts(self):
        if self.failed_count > self.document_count:
            raise ValueError("failed_count exceeds document_count")
        for fields in (self.agreement_fields, self.requested_fields):
            if len(fields) > 32 or len(fields) != len(set(fields)):
                raise ValueError("field lists must be unique and contain at most 32 fields")
            if any(not f or len(f) > 64 or not f.replace("_", "").isalnum() for f in fields):
                raise ValueError("invalid field identifier")
        if not self.agreement_fields:
            raise ValueError("original scope requires at least one field")
        return self


class Command(Mutation):
    verb: Literal[
        "correct",
        "accept_delivery",
        "open_dispute",
        "answer",
        "amend_agreement",
        "approve_action",
        "decline_action",
        "execute_action",
        "accept_change",
        "authorize_change",
        "decline_change",
        "receive_payment",
        "fulfill_change",
        "accept_change_delivery",
        "reconcile",
        "handoff",
        "verify_base",
        "accept_base",
        "quote_processing",
        "accept_processing_quote",
    ]
    job_ids: list[str] = Field(default_factory=list)
    issue_id: str | None = None
    question_id: str | None = None
    action_id: str | None = None
    approval_id: str | None = None
    change_order_id: str | None = None
    operation_id: str | None = None
    processing_quote_id: str | None = None
    amount_minor: Cents | None = None
    text: str | None = None
    fields: list[str] = Field(default_factory=list)
    effective_at: datetime | None = None
    amendment_id: str | None = None
    provider_outcome: Literal["SUCCESS", "FAILURE", "UNKNOWN"] = "SUCCESS"


class InvestigationRequest(Mutation):
    issue_id: Identifier
    mode: Literal["DETERMINISTIC", "ANTHROPIC"] = "DETERMINISTIC"


class DocumentUpload(Mutation):
    filename: str
    media_type: Literal["text/plain", "application/pdf", "application/json", "text/csv"]
    content_base64: str
    kind: Literal["agreement", "amendment", "message", "source"] = "message"
    issue_id: str | None = None


class InvestigationOutcome(Model):
    issue_id: Identifier
    revision: Revision
    findings: list[Finding]
    questions: list[Question]
    recommendations: list[Literal["INCLUDED_FIELD", "QUOTE", "HUMAN_REVIEW", "NO_REMEDY"]]
    summary: str
    model_mode: Literal["DETERMINISTIC", "ANTHROPIC"]
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str | None = None


class ContractExport(Model):
    order: OrderView
    event: Event
    create: OrderCreate
    command: Command
    investigation_request: InvestigationRequest
    outcome: InvestigationOutcome
    upload: DocumentUpload
    actor: Actor
