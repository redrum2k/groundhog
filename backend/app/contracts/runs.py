"""Pydantic source of truth for the existing DatumCo run canvas and live commands."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictInt, TypeAdapter

from app.contracts.catalog import Quote, RequestDraft
from app.contracts.data_product import Frozen, Name
from app.contracts.dataset import DatasetComplaintTarget, DatasetReference
from app.contracts.payments import (
    FundingAuthorization,
    FundingPreparation,
    PaymentAccountState,
    PaymentView,
)

Track = Literal["shared", "red", "green", "amber"]
StepKind = Literal[
    "clarify",
    "paid",
    "produce",
    "review",
    "captured",
    "investigate",
    "verdict",
    "amend",
    "grey",
    "decide",
]
ControllerAction = Literal["approve", "reject", "ask", "escalate"]


class ContractLine(Frozen):
    id: str
    text: str
    check: Literal["schema", "code"]


class DataContract(Frozen):
    version: int
    buyer: str
    title: str
    price: int
    lines: list[ContractLine]


class CanvasBinding(Frozen):
    deliveryVersion: int
    evidenceVersion: int
    runId: str | None = None
    orderId: str | None = None
    snapshotId: str | None = None
    revision: int | None = None


class DecisionBinding(CanvasBinding):
    runId: Name
    orderId: Name
    snapshotId: Name
    revision: Annotated[StrictInt, Field(ge=1)]
    deliveryVersion: Annotated[StrictInt, Field(ge=0)]
    evidenceVersion: Annotated[StrictInt, Field(ge=1)]


class MessageSource(Frozen):
    kind: Literal["message"] = "message"
    messageId: str


class CellSource(Frozen):
    kind: Literal["cell"] = "cell"
    version: int
    row: str
    column: str
    reference: DatasetReference | None = None


class NoSource(Frozen):
    kind: Literal["none"] = "none"
    reason: str


Source = MessageSource | CellSource | NoSource


class EvidenceBase(Frozen):
    id: str
    label: str
    note: str
    source: Source


class InterviewEvidence(EvidenceBase):
    kind: Literal["interview_quote", "claim"]
    speaker: str
    quote: str


class CellEvidence(EvidenceBase):
    kind: Literal["sheet_cell"] = "sheet_cell"
    file: str
    row: str
    column: str
    value: str | None


class CategoryEvidence(EvidenceBase):
    kind: Literal["vendor_category"] = "vendor_category"
    vendor: str
    item: str
    category: str


Evidence = InterviewEvidence | CellEvidence | CategoryEvidence


class ChecklistAttachment(Frozen):
    kind: Literal["checklist"] = "checklist"


class EvidenceAttachment(Frozen):
    kind: Literal["evidence"] = "evidence"
    evidenceId: str


class Message(Frozen):
    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always", populate_by_name=True
    )
    id: str
    from_: Literal["buyer", "agent", "controller"] = Field(alias="from")
    text: str
    asks: str | None = None
    attach: list[ChecklistAttachment | EvidenceAttachment] = []


class Step(Frozen):
    id: str
    kind: StepKind
    title: str
    detail: str
    panel: bool = False


class ZipCount(Frozen):
    zip: str
    area: str
    count: int | None
    flag: Literal["withheld", "missing", "added", "yoga"] | None = None
    status: Literal["released", "suppressed", "unknown"] | None = None


class CanvasDelivery(Frozen):
    version: int
    file: str
    rows: list[ZipCount]
    reviewClosesAt: str | None = None
    artifactId: str | None = None
    sha256: str | None = None
    previewArtifactId: str | None = None


class Dispute(Frozen):
    id: str
    claim: str
    raisedBy: str


class Verdict(Frozen):
    kind: Literal["agree", "disagree", "grey"]
    reason: str
    decidedBy: Literal["rules", "controller", "contract"]
    evidenceIds: list[str]


class CanvasPayment(Frozen):
    id: str
    amount: int
    rail: Literal["commerce-payments", "mock"] = "commerce-payments"
    network: Literal["base-sepolia"] = "base-sepolia"
    mock: bool


class CanvasAmendment(Frozen):
    id: str
    summary: str
    price: int
    line: ContractLine


class RuleUpdate(Frozen):
    id: str
    label: str
    text: str
    decidedBy: str
    activationId: str | None = None
    scope: str | None = None
    version: str | None = None
    illustration: bool = False


class JournalEntry(Frozen):
    id: str
    memo: str
    debit: str
    credit: str
    amount: int


class Margin(Frozen):
    revenue: int
    cost: int | None


class BaseEvent(Frozen):
    seq: Annotated[int, Field(ge=1)]
    at: AwareDatetime
    track: Track = "shared"


class StepEvent(BaseEvent):
    step: str
    attempt: Annotated[int, Field(ge=1)] = 1


class StepsPlanned(BaseEvent):
    type: Literal["steps_planned"]
    steps: list[Step]


class StepStarted(StepEvent):
    type: Literal["step_started", "step_completed"]


class StepWaiting(StepEvent):
    type: Literal["step_waiting"]
    waitingOn: str


class MessageEvent(StepEvent):
    type: Literal["message"]
    message: Message


class ContractLineEvent(StepEvent):
    type: Literal["contract_line_asked", "contract_line_drafted", "contract_line_approved"]
    line: ContractLine


class ContractApproved(StepEvent):
    type: Literal["contract_approved"]
    contract: DataContract
    allowedBy: str


class DeliveryReady(StepEvent):
    type: Literal["delivery_ready"]
    delivery: CanvasDelivery


class CheckPassed(StepEvent):
    type: Literal["check_passed"]
    lineId: str
    detail: str | None = None


class CheckFailed(StepEvent):
    type: Literal["check_failed"]
    lineId: str
    reason: str
    assessment: Literal["FAIL", "UNKNOWN", "CONFLICT"] = "FAIL"


class CheckFixed(StepEvent):
    type: Literal["check_fixed"]
    lineId: str
    fix: str


class EvidenceFound(StepEvent):
    type: Literal["evidence_found"]
    evidence: Evidence


class DisputeOpened(StepEvent):
    type: Literal["dispute_opened"]
    dispute: Dispute


class VerdictEvent(StepEvent):
    type: Literal["verdict"]
    verdict: Verdict
    allowedBy: str


class ControllerDecided(StepEvent):
    type: Literal["controller_decided"]
    action: ControllerAction
    by: str
    note: str
    binding: CanvasBinding


class AmendmentSigned(StepEvent):
    type: Literal["amendment_signed"]
    amendment: CanvasAmendment
    allowedBy: str


class RuleUpdated(StepEvent):
    type: Literal["rule_updated"]
    rule: RuleUpdate


class BooksPosted(StepEvent):
    type: Literal["books_posted"]
    entries: list[JournalEntry]
    margin: Margin | None = None
    operationIds: list[str] = []
    note: str | None = None


class PaymentAuthorized(BaseEvent):
    type: Literal["payment_authorized"]
    payment: CanvasPayment
    allowedBy: str


class PaymentCaptured(BaseEvent):
    type: Literal["payment_captured"]
    paymentId: str
    captureTx: str | None
    allowedBy: str


class PaymentStateChanged(BaseEvent):
    type: Literal["payment_state_changed"]
    payment: CanvasPayment
    state: PaymentAccountState
    reason: str | None = None


class StateChanged(StepEvent):
    type: Literal["state_changed"]
    state: str
    reason: str | None = None
    binding: CanvasBinding
    paymentState: PaymentAccountState | None = None


RunEvent = Annotated[
    StepsPlanned
    | StepStarted
    | StepWaiting
    | MessageEvent
    | ContractLineEvent
    | ContractApproved
    | DeliveryReady
    | CheckPassed
    | CheckFailed
    | CheckFixed
    | EvidenceFound
    | DisputeOpened
    | VerdictEvent
    | ControllerDecided
    | AmendmentSigned
    | RuleUpdated
    | BooksPosted
    | PaymentAuthorized
    | PaymentCaptured
    | PaymentStateChanged
    | StateChanged,
    Field(discriminator="type"),
]
EVENT_ADAPTER = TypeAdapter(RunEvent)


class RunCreate(Frozen):
    prompt: Annotated[str, Field(min_length=1, max_length=4000)] = (
        "SF adults 25–34 interested in fitness, counts by ZIP."
    )
    corpus_id: Literal["sf-aggregate-v1"] = "sf-aggregate-v1"


class RunCreated(Frozen):
    id: str
    poll_after_ms: Literal[1000] = 1000


class ActionAvailability(Frozen):
    action: str
    enabled: bool
    reason: str


class RunPage(Frozen):
    events: list[RunEvent]
    poll_after_ms: Literal[1000] = 1000
    next_after: int
    high_watermark: int
    caught_up: bool
    server_time: AwareDatetime
    binding: DecisionBinding | None
    available_actions: list[ActionAvailability]
    request: RequestDraft
    quote: Quote | None
    payment: PaymentView | None
    reviewClosesAt: AwareDatetime | None
    disputeClosesAt: AwareDatetime | None
    captureClosesAt: AwareDatetime | None
    latestSafeSubmissionAt: AwareDatetime | None
    evidence_request: "RunEvidenceRequest | None" = None
    complaint_targets: tuple[DatasetComplaintTarget, ...] = ()


class RunEvidenceRequest(Frozen):
    request_id: Name
    case_id: Name | None
    prompt: str
    deadline: AwareDatetime
    references_required: bool
    allowed_references: Annotated[tuple[DatasetReference, ...], Field(max_length=32)] = ()


class RunDecision(Frozen):
    action: ControllerAction
    binding: DecisionBinding
    reason: Annotated[str, Field(min_length=1, max_length=1200)] = (
        "Review current cited evidence and the proposed remedy."
    )
    evidence_ids: tuple[Name, ...] = ()


class DecisionAcknowledgement(Frozen):
    ok: Literal[True] = True
    decision_id: str


class RunOffer(Frozen):
    binding: DecisionBinding
    scope: Literal["oakland", "yoga", "replacement"]


class RunEvidenceAnswer(Frozen):
    binding: DecisionBinding
    # Absent only for read-only replay of pre-remediation acknowledgements.
    request_id: Name | None = None
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    references: Annotated[tuple[DatasetReference, ...], Field(max_length=8)] = ()


class ResolvedCell(Frozen):
    kind: Literal["cell"] = "cell"
    reference: DatasetReference
    value: str | None


class ResolvedMessage(Frozen):
    kind: Literal["message"] = "message"
    message: Message


EvidenceResolution = ResolvedCell | ResolvedMessage


class RunContractExport(Frozen):
    event: RunEvent
    page: RunPage
    create: RunCreate
    created: RunCreated
    decision: RunDecision
    acknowledgement: DecisionAcknowledgement
    offer: RunOffer
    answer: RunEvidenceAnswer

    funding_preparation: FundingPreparation
    funding_authorization: FundingAuthorization

    resolution: EvidenceResolution
