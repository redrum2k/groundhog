from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Version = Annotated[StrictInt, Field(ge=1)]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class Money(Contract):
    """Integer minor units; asset identity/chain mapping awaits the payment spike."""

    amount_minor: Annotated[StrictInt, Field(gt=0)]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{2,11}$")]
    decimals: Annotated[StrictInt, Field(ge=0, le=18)]


class AcceptedPolicy(Contract):
    policy_version: Text
    review_window_seconds: Literal[60] = 60
    free_regenerations: Literal[1] = 1


class EvidencePointer(Contract):
    evidence_id: Text
    version: Version
    sha256: Digest


class EvidenceReference(EvidencePointer):
    storage_key: Text
    media_type: Text
    kind: Literal[
        "accepted_input",
        "delivery_artifact",
        "customer_evidence",
        "verification_report",
        "structured_data",
    ]
    derived_from: tuple[EvidencePointer, ...] = ()

    @model_validator(mode="after")
    def require_structured_data_provenance(self) -> Self:
        if self.kind == "structured_data" and not self.derived_from:
            raise ValueError("structured data must reference its exact source evidence")
        return self


def unique_evidence(references: tuple[EvidenceReference, ...]) -> None:
    if len({item.evidence_id for item in references}) != len(references):
        raise ValueError("an evidence set must contain one version per evidence_id")


def validate_structured_data(
    sidecars: tuple[EvidenceReference, ...], sources: tuple[EvidenceReference, ...]
) -> None:
    unique_evidence((*sources, *sidecars))
    source_versions = {(item.evidence_id, item.version, item.sha256) for item in sources}
    for sidecar in sidecars:
        if sidecar.kind != "structured_data" or any(
            (item.evidence_id, item.version, item.sha256) not in source_versions
            for item in sidecar.derived_from
        ):
            raise ValueError("structured data must bind the exact source artifact versions")


class OrderSnapshot(Contract):
    order_id: Text
    snapshot_id: Text
    accepted_at: AwareDatetime
    accepted_brief: Text
    input_versions: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    structured_data: tuple[EvidenceReference, ...] = ()
    price: Money
    policy: AcceptedPolicy

    @model_validator(mode="after")
    def check_inputs(self) -> Self:
        unique_evidence(self.input_versions)
        if any(item.kind != "accepted_input" for item in self.input_versions):
            raise ValueError("snapshot inputs must be accepted_input evidence")
        validate_structured_data(self.structured_data, self.input_versions)
        return self


class DeliveryVersion(Contract):
    order_id: Text
    snapshot_id: Text
    version: Version
    delivered_at: AwareDatetime
    artifacts: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    structured_data: tuple[EvidenceReference, ...] = ()

    @model_validator(mode="after")
    def check_artifacts(self) -> Self:
        unique_evidence(self.artifacts)
        if any(item.kind != "delivery_artifact" for item in self.artifacts):
            raise ValueError("delivery artifacts must be delivery_artifact evidence")
        validate_structured_data(self.structured_data, self.artifacts)
        return self


class ProposalBinding(Contract):
    order_id: Text
    snapshot_id: Text
    delivery_version: Version
    evidence_version: Version
    proposal_version: Version


class InvestigationInput(Contract):
    case_id: Text
    snapshot: OrderSnapshot
    delivery: DeliveryVersion
    proposal: ProposalBinding
    complaint: Text
    evidence: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    free_regenerations_used: Annotated[StrictInt, Field(ge=0, le=1)] = 0

    @model_validator(mode="after")
    def check_binding(self) -> Self:
        unique_evidence(self.evidence)
        if (
            self.proposal.order_id != self.snapshot.order_id
            or self.proposal.snapshot_id != self.snapshot.snapshot_id
            or self.delivery.order_id != self.snapshot.order_id
            or self.delivery.snapshot_id != self.snapshot.snapshot_id
            or self.proposal.delivery_version != self.delivery.version
        ):
            raise ValueError("investigation must bind the accepted snapshot and exact delivery")
        if self.delivery.delivered_at < self.snapshot.accepted_at:
            raise ValueError("delivery cannot precede acceptance")
        required = (
            *self.snapshot.input_versions,
            *self.snapshot.structured_data,
            *self.delivery.artifacts,
            *self.delivery.structured_data,
        )
        if not set(required).issubset(self.evidence):
            raise ValueError(
                "evidence must include the exact accepted inputs and delivery artifacts"
            )
        return self


Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class PdfHighlight(Contract):
    """One-based page; normalized rectangle on the displayed page, top-left origin."""

    page_number: Version
    x0: Coordinate
    y0: Coordinate
    x1: Coordinate
    y1: Coordinate

    @model_validator(mode="after")
    def check_rectangle(self) -> Self:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError("highlight must have positive width and height")
        return self


class Citation(EvidencePointer):
    locator: Text  # Format-independent: page, cell, line, region, etc.
    highlights: tuple[PdfHighlight, ...] = ()


class Finding(Contract):
    statement: Text
    citations: Annotated[tuple[Citation, ...], Field(min_length=1)]


class Recommendation(Contract):
    action: Literal["free_regeneration", "human_review", "no_remedy"]
    rationale: Text


class InvestigationResult(Contract):
    case_id: Text
    proposal: ProposalBinding
    findings: tuple[Finding, ...]
    unresolved_issues: tuple[Text, ...]
    questions: tuple[Text, ...]
    recommendations: Annotated[tuple[Recommendation, ...], Field(min_length=1)]

    def validate_for(self, request: InvestigationInput) -> None:
        """Runtime calls this before storing/using an untrusted investigator result."""
        if self.case_id != request.case_id or self.proposal != request.proposal:
            raise ValueError("stale or unrelated investigation result")
        allowed = {(item.evidence_id, item.version, item.sha256): item for item in request.evidence}
        for finding in self.findings:
            for citation in finding.citations:
                reference = allowed.get((citation.evidence_id, citation.version, citation.sha256))
                if reference is None:
                    raise ValueError(
                        "citation must refer to exact evidence supplied to the investigator"
                    )
                if reference.media_type == "application/pdf" and not citation.highlights:
                    raise ValueError("PDF citations require linked evidence highlights")
                if reference.media_type != "application/pdf" and citation.highlights:
                    raise ValueError("PDF highlights must link to PDF evidence")


class SettlementIntent(Contract):
    """Proposed operation only; schema validity does not confer execution authority."""

    proposal: ProposalBinding
    action: Literal["capture", "release"]
    amount: Money
    authorization_id: Text
    idempotency_key: Text


class OrderState(StrEnum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    HUMAN_REVIEW = "human_review"
    CLOSED = "closed"


class DeliveryState(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    PASSED = "passed"
    FAILED = "failed"


class CaseState(StrEnum):
    NONE = "none"
    OPEN = "open"
    RESOLVED = "resolved"
    HUMAN_REVIEW = "human_review"


class PaymentState(StrEnum):
    UNAUTHORIZED = "unauthorized"
    AUTHORIZED = "authorized"
    SUBMITTED = "submitted"
    UNCERTAIN = "uncertain"
    CAPTURED = "captured"
    RELEASED = "released"
    EXPIRED = "expired"
    MOCK = "mock"
