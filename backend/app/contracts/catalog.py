"""v0.3 catalog contracts. Model suggestions never carry commercial authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.contracts.dataset import BrokeragePolicy, DatasetReference, DatasetSpecification
from app.contracts.models import Contract, Digest, Money, PdfHighlight, Text, Version
from app.contracts.payments import Address, PaymentTerms, PaymentView
from app.payments.interfaces import PaymentReceipt

Nonnegative = Annotated[StrictInt, Field(ge=0)]
PositiveDecimal = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Result = Literal["PASS", "FAIL", "UNKNOWN", "CONFLICT"]
Blocker = Literal[
    "SOURCE_AUTHORITY_UNVERIFIED", "EFFECTIVE_DATE_CONFLICT", "REQUIRED_VALUE_UNREADABLE"
]


class Artifact(Contract):
    artifact_id: Text
    version: Version = 1
    sha256: Digest
    storage_key: Text
    media_type: Literal["application/pdf", "application/json", "text/csv"]


class Span(Contract):
    artifact_id: Text
    sha256: Digest
    page: Version
    start: Nonnegative
    end: Version
    quote: Text
    highlight: PdfHighlight

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start or self.highlight.page_number != self.page:
            raise ValueError("invalid citation span")
        return self


class Source(Contract):
    source_id: Text
    version: Version
    corpus_id: Text
    supplier_id: Text
    edition: Text
    effective_date: date
    artifact: Artifact
    authority: Literal["registered_supplier_publication", "authorized_representative", "unverified"]
    authority_record: Text | None = None

    @model_validator(mode="after")
    def authority_evidence(self):
        if self.authority != "unverified" and not self.authority_record:
            raise ValueError("trusted registry authority requires a recorded basis")
        return self


class SourcePolicy(Contract):
    precedence: Literal["frozen_edition_only"] = "frozen_edition_only"
    accepted_authority: tuple[
        Literal["registered_supplier_publication", "authorized_representative"], ...
    ] = ("registered_supplier_publication", "authorized_representative")
    evidence_repair: Literal["preauthorized", "customer_and_provider"] = "preauthorized"
    substantive_change: Literal["customer_and_provider"] = "customer_and_provider"


class Terms(Contract):
    corpus_id: Text
    category: Literal["storage"] = "storage"
    weight_concept: Literal["net_unit", "shipping"]
    weight_unit: Literal["kg", "g"] = "kg"
    weight_operator: Literal["lt", "lte"]
    weight_threshold: PositiveDecimal
    price_basis: Literal["unit"] = "unit"
    currency: Literal["USD"] = "USD"
    price_operator: Literal["lt", "lte"]
    price_threshold: PositiveDecimal
    required_fields: tuple[
        Literal["product_id", "name", "supplier", "weight", "unit_price", "citation"], ...
    ] = ("product_id", "name", "supplier", "weight", "unit_price", "citation")
    completeness: Literal["all_qualifying_records"] = "all_qualifying_records"
    unknown_values: Literal["explicit_unresolved_and_block_if_material"] = (
        "explicit_unresolved_and_block_if_material"
    )
    source_policy: SourcePolicy = SourcePolicy()

    @model_validator(mode="after")
    def required_output(self):
        if (
            set(self.required_fields)
            != {"product_id", "name", "supplier", "weight", "unit_price", "citation"}
            or len(self.required_fields) != 6
        ):
            raise ValueError("all six catalog output fields are mandatory")
        return self


class Requirement(Contract):
    requirement_id: Text
    wording: Text
    check: Literal[
        "category",
        "weight",
        "price",
        "fields",
        "completeness",
        "provenance",
        "pdf",
        "cohort",
        "geography",
        "schema",
        "coverage",
        "suppression",
        "artifact",
    ]


class Specification(Contract):
    revision: Version
    terms: Terms | DatasetSpecification
    requirements: tuple[Requirement, ...]
    summary: Text
    limitations: tuple[Text, ...]


class Clarification(Contract):
    question_id: Text
    prompt: Text
    field: Text


class CompilerOutput(Contract):
    terms: Terms | DatasetSpecification | None
    question: Clarification | None
    summary: Text
    limitations: tuple[Text, ...]

    @model_validator(mode="after")
    def one_outcome(self):
        if (self.terms is None) == (self.question is None):
            raise ValueError("draft either asks one question or supplies terms")
        return self


class ClarificationAnswer(Contract):
    question_id: Text
    text: Text


class RequestDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    request_id: Text
    revision: Version = 1
    prompt: Text
    corpus_id: Text
    created_at: AwareDatetime
    deadline: AwareDatetime
    status: Literal["compiling", "clarification", "ready", "accepted", "human_review"] = "compiling"
    questions_asked: Nonnegative = 0
    answers: tuple[ClarificationAnswer, ...] = ()
    question: Clarification | None = None
    specification: Specification | None = None
    compiler_calls: Nonnegative = 0
    error: Text | None = None
    order_id: Text | None = None


class Policy(Contract):
    version: Literal["catalog-v0.3"] = "catalog-v0.3"
    review_seconds: Literal[60] = 60
    dispute_seconds: Literal[60] = 60
    evidence_repair_seconds: Literal[120] = 120
    evidence_attempts: Literal[2] = 2
    max_questions: Literal[2] = 2
    free_corrections: Literal[1] = 1
    authorization_seconds: Literal[3600] = 3600
    clarification_seconds: Literal[300] = 300
    clarification_rounds: Literal[3] = 3


class Quote(Contract):
    quote_id: Text
    request_id: Text
    request_revision: Version
    specification: Specification
    sources: tuple[Source, ...]
    amount: Money
    payment_terms: PaymentTerms | None = None
    policy: Policy | BrokeragePolicy = Policy()
    expires_at: AwareDatetime
    purpose: Literal["initial", "additional_work", "substantive_amendment"] = "initial"
    work_description: Text
    parent_order_id: Text | None = None
    parent_binding: Binding | None = None
    amendment_id: Text | None = None
    provider_actor: Text = "server:catalog-price-v1"

    @model_validator(mode="after")
    def coherent_manifest(self):
        if not self.sources or len({s.source_id for s in self.sources}) != len(self.sources):
            raise ValueError("quote requires a nonempty, unique source manifest")
        if any(s.corpus_id != self.specification.terms.corpus_id for s in self.sources):
            raise ValueError("quoted sources must belong to the selected corpus")
        dataset = isinstance(self.specification.terms, DatasetSpecification)
        if dataset != isinstance(self.policy, BrokeragePolicy):
            raise ValueError("accepted domain and policy must match")
        if dataset:
            terms = self.specification.terms
            pins = tuple((s.source_id, s.version, s.artifact.sha256) for s in self.sources)
            if pins != tuple((s.source_id, s.version, s.sha256) for s in terms.sources):
                raise ValueError("specification source pins must match the quoted manifest")
        return self


class Snapshot(Contract):
    schema_version: Literal[3, 4] = 3
    snapshot_id: Text
    order_id: Text
    quote: Quote
    accepted_at: AwareDatetime
    customer_actor: Text


class Binding(Contract):
    snapshot_id: Text
    evidence_revision: Version
    delivery_version: Nonnegative


Quote.model_rebuild()


class Provenance(Contract):
    kind: Literal["deterministic", "model"]
    assessor: Text
    version: Text
    model_score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None


class Obligation(Contract):
    obligation_id: Text
    requirement_id: Text
    subject: Text
    field: Text
    check: Text
    dependencies: tuple[Text, ...] = ()
    mandatory: bool = True
    decision_effect: Literal["compliance", "remedy", "settlement", "none"] = "compliance"


class Assessment(Contract):
    obligation_id: Text
    result: Result
    citations: tuple[Span | DatasetReference, ...] = ()
    missing_facts: tuple[Text, ...] = ()
    conflicting_evidence: tuple[Span | DatasetReference, ...] = ()
    reason_code: Text
    explanation: Text
    requested_evidence: Text | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def grounded(self):
        if self.result in ("PASS", "FAIL", "CONFLICT") and not self.citations:
            raise ValueError("established results require citations")
        if self.result == "UNKNOWN" and not self.missing_facts:
            raise ValueError("unknown result requires a missing fact")
        if self.result == "CONFLICT" and not self.conflicting_evidence:
            raise ValueError("conflict requires conflicting evidence")
        return self


class Verification(Contract):
    binding: Binding
    stage: Literal["fulfillment", "delivery", "dispute"]
    obligations: tuple[Obligation, ...]
    assessments: tuple[Assessment, ...]
    material_blockers: tuple[Text, ...]
    provider_defect: bool
    passed: bool
    created_at: AwareDatetime

    @model_validator(mode="after")
    def complete_assessments(self):
        identifiers = tuple(o.obligation_id for o in self.obligations)
        if len(set(identifiers)) != len(identifiers) or identifiers != tuple(
            a.obligation_id for a in self.assessments
        ):
            raise ValueError("each obligation requires one assessment in registry order")
        if self.passed and (
            self.material_blockers
            or self.provider_defect
            or any(
                o.mandatory and a.result != "PASS"
                for o, a in zip(self.obligations, self.assessments, strict=True)
            )
        ):
            raise ValueError("passing verification cannot contain mandatory failures or blockers")
        return self


class Product(Contract):
    product_id: Text
    name: Text
    category: Text
    supplier_id: Text
    source_id: Text
    net_kg: Decimal | None
    shipping_kg: Decimal | None
    unit_price: Decimal | None
    currency: Text
    citations: tuple[Span, ...]


class ExtractedSource(Contract):
    source: Source
    edition: Text
    effective_date: date
    declared_ids: tuple[Text, ...]
    products: tuple[Product, ...]
    header: Span
    index_citations: tuple[Span, ...] = ()
    parse_errors: tuple[Text, ...] = ()


class Delivery(Contract):
    version: Version
    pdf: Artifact
    sidecar: Artifact
    published_at: AwareDatetime
    review_deadline: AwareDatetime
    binding: Binding


class DatasetDelivery(Contract):
    domain: Literal["aggregate_dataset"] = "aggregate_dataset"
    version: Version
    csv: Artifact
    preview: Artifact
    published_at: AwareDatetime
    review_deadline: AwareDatetime
    binding: Binding


class EvidenceRequest(Contract):
    request_id: Text
    obligation_ids: tuple[Text, ...]
    target_source: Source
    prompt: Text
    round: Version
    deadline: AwareDatetime
    answered: bool = False


class Amendment(Contract):
    amendment_id: Text
    actor: Text
    target_source_id: Text
    target_version: Version
    evidence_request_id: Text
    reason: Text
    artifact: Artifact
    relationship: Literal["replacement_page", "supplement"]
    submitted_at: AwareDatetime
    classification: Literal["pending", "evidence_only", "substantive", "unresolved"] = "pending"
    assessment: tuple[Assessment, ...] = ()
    applied_revision: Version | None = None
    history: tuple[Text, ...] = ()


class Approval(Contract):
    approval_id: Text
    amendment_id: Text
    binding: Binding
    status: Literal["pending", "approved", "rejected", "invalidated"] = "pending"
    customer_actor: Text | None = None
    provider_actor: Text | None = None
    reason: Text


class Complaint(Contract):
    text: Text
    product_id: Text
    field: Literal[
        "weight",
        "unit_price",
        "completeness",
        "provenance",
        "pdf",
        "cohort",
        "category",
        "geography",
        "coverage",
        "suppression",
        "artifact",
    ]
    requirement_id: Text
    artifact_id: Text
    intent: Literal["dispute_fact", "change_scope"] = "dispute_fact"


class Case(Contract):
    case_id: Text
    complaint: Complaint
    opened_at: AwareDatetime
    deadline: AwareDatetime
    status: Literal["open", "supported", "unsupported", "scope_change", "human_review"] = "open"
    questions_asked: Nonnegative = 0
    question: Text | None = None
    answers: tuple[Text, ...] = ()


class Authorization(Contract):
    authorization_id: Text
    amount: Money
    expires_at: AwareDatetime
    status: Literal["pending", "mock_authorized", "authorized", "uncertain", "expired", "released"]
    receipt: PaymentReceipt | None = None


class Booking(Contract):
    operation_id: Text
    kind: Literal["capture", "release"]
    amount: Money
    recorded_at: AwareDatetime
    binding: Binding
    receipt: PaymentReceipt


class Job(Contract):
    job_id: Text
    kind: Literal["fulfill", "correct", "reverify"]
    binding: Binding
    status: Literal["queued", "running", "done", "failed", "stale"] = "queued"
    attempts: Nonnegative = 0
    lease_token: Text | None = None
    lease_until: AwareDatetime | None = None
    error: Text | None = None


class ReviewRow(Contract):
    requirement_id: Text
    accepted_wording: Text
    product: Text
    field: Text
    issue: Text
    source_fact: Text
    source_citations: tuple[Span | DatasetReference, ...]
    delivered_value: Text | None
    delivered_citations: tuple[Span | DatasetReference, ...]
    result: Result
    amendment_status: Text
    missing_fact_or_contradiction: Text
    recommended_remedy: Text
    financial_effect: Text
    required_authority: Text


class ReviewerDecision(Contract):
    actor: Text
    action: Literal[
        "request_evidence", "release_authorization", "propose_exception", "reject", "escalate"
    ]
    reason: Text
    supporting_evidence: tuple[Span | DatasetReference, ...]
    binding: Binding
    recorded_at: AwareDatetime
    negotiated_exception: bool = False


class CatalogOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal[3, 4] = 3
    payment_id: Text | None = None
    snapshot: Snapshot
    revision: Version = 1
    binding: Binding
    order_state: Literal[
        "awaiting_authorization",
        "processing",
        "waiting_evidence",
        "pending_approval",
        "delivered",
        "human_review",
        "operational_failure",
        "closed",
    ] = "processing"
    delivery_state: Literal["absent", "verified", "needs_review", "operational_failure"] = "absent"
    authority_state: Literal[
        "clear", "pending_source_authority", "pending_consent", "rejected", "human_review"
    ] = "clear"
    authorization: Authorization
    sources: tuple[Source, ...]
    artifacts: tuple[Artifact, ...]
    deliveries: tuple[Delivery | DatasetDelivery, ...] = ()
    verification: Verification | None = None
    verification_history: tuple[Verification, ...] = ()
    evidence_requests: tuple[EvidenceRequest, ...] = ()
    repair_deadline: AwareDatetime | None = None
    amendments: tuple[Amendment, ...] = ()
    approvals: tuple[Approval, ...] = ()
    cases: tuple[Case, ...] = ()
    jobs: tuple[Job, ...] = ()
    ledger: tuple[Booking, ...] = ()
    free_corrections_used: Annotated[StrictInt, Field(ge=0, le=1)] = 0
    customer_acceptance: Binding | None = None
    decisions: tuple[ReviewerDecision, ...] = ()
    semantic_findings: tuple[Assessment, ...] = ()
    error: Text | None = None
    children: tuple[Text, ...] = ()


class RequestCommand(Contract):
    prompt: Annotated[str, Field(min_length=1, max_length=4000)]
    corpus_id: Text
    idempotency_key: Text


class RevisionCommand(Contract):
    expected_revision: Version
    idempotency_key: Text


class QuoteRequest(RevisionCommand):
    payer: Address | None = None


class ClarifyCommand(RevisionCommand):
    question_id: Text
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class AcceptQuoteCommand(Contract):
    quote_id: Text
    customer_actor: Text
    idempotency_key: Text


class OrderCommand(RevisionCommand):
    expected_binding: Binding


class DisputeCommand(OrderCommand):
    complaint: Complaint


class AnswerCommand(OrderCommand):
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class UploadCommand(OrderCommand):
    evidence_request_id: Text
    actor: Text
    reason: Text
    relationship: Literal["replacement_page", "supplement"]
    pdf_base64: Annotated[str, Field(min_length=1, max_length=2800000)]


class ApprovalCommand(OrderCommand):
    approval_id: Text
    actor: Text
    accept: bool


class OfferCommand(OrderCommand):
    work_description: Text
    terms: Terms
    amendment_id: Text | None = None


class ReviewCommand(OrderCommand):
    action: Literal["request_evidence", "release_authorization", "propose_exception"]
    reason: Text
    supporting_evidence: Annotated[tuple[Span, ...], Field(min_length=1)]


class OrderView(Contract):
    order: CatalogOrder
    server_time: AwareDatetime
    available_actions: tuple[
        Literal[
            "accept",
            "dispute",
            "answer",
            "upload_evidence",
            "approve_amendment",
            "prepare_funding",
            "submit_funding_authorization",
        ],
        ...,
    ]
    poll_after_ms: Literal[2000] = 2000
    human_review: tuple[ReviewRow, ...]
    payment_mode: Literal["mock", "base_sepolia"] = "mock"
    payment: PaymentView | None = None


# Contexts are deliberately distinct: pre-delivery work never needs a fake PDF.
class PrecontractContext(Contract):
    draft: RequestDraft
    sources: tuple[Source, ...]
    source_observations: tuple[Text, ...] = ()


class FulfillmentContext(Contract):
    snapshot: Snapshot
    binding: Binding
    sources: tuple[Source, ...]


class EvidenceRepairContext(Contract):
    fulfillment: FulfillmentContext
    request: EvidenceRequest
    amendment: Amendment


class DisputeContext(Contract):
    fulfillment: FulfillmentContext
    delivery: Delivery
    case: Case


class RegressionRuleProposal(Contract):
    """Offline evaluation extension only; never self-installs runtime checks."""

    description: Text
    evidence_ids: tuple[Text, ...]
    proposed_by: Text


class CatalogContractExport(Contract):
    request: RequestCommand
    draft: RequestDraft
    revision: RevisionCommand
    clarify: ClarifyCommand
    quote_request: QuoteRequest
    quote: Quote
    acceptance: AcceptQuoteCommand
    order: OrderView
    command: OrderCommand
    dispute: DisputeCommand
