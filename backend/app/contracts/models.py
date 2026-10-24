"""v0.2 historical DTOs and shared primitives. Invoice records are read-only in v0.3.

Old policy fields are retained only to deserialize historical records without rewriting them.
Use contracts.catalog for every new request, order, assessment and commercial decision.
"""

from __future__ import annotations

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

from app.contracts.data_product import DataSpecification, RequirementAssessment

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
    review_window_seconds: Literal[600] = 600
    free_regenerations: Literal[1] = 1
    max_questions: Literal[2] = 2
    max_question_rounds: Literal[2] = 2
    additional_processing_price: Money | None = None


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
    job_type: Literal["invoice_register", "regional_market_intelligence"] = "invoice_register"
    order_id: Text
    snapshot_id: Text
    accepted_at: AwareDatetime
    accepted_brief: Text
    input_versions: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    structured_data: tuple[EvidenceReference, ...] = ()
    price: Money
    policy: AcceptedPolicy
    data_specification: DataSpecification | None = None

    @model_validator(mode="after")
    def check_inputs(self) -> Self:
        if self.job_type == "regional_market_intelligence":
            if (
                self.data_specification is None
                or self.policy.policy_version != "broker-review-v0.3"
            ):
                raise ValueError(
                    "broker orders require their accepted specification and v0.3 policy"
                )
            if self.policy.additional_processing_price is not None:
                raise ValueError("broker review has no automatic refutation fee")
        elif (
            self.data_specification is not None
            or self.policy.policy_version == "broker-review-v0.3"
        ):
            raise ValueError("broker policy and data specification require the broker profile")
        unique_evidence(self.input_versions)
        if any(item.kind != "accepted_input" for item in self.input_versions):
            raise ValueError("snapshot inputs must be accepted_input evidence")
        validate_structured_data(self.structured_data, self.input_versions)
        extra_price = self.policy.additional_processing_price
        if extra_price and (extra_price.currency, extra_price.decimals) != (
            self.price.currency,
            self.price.decimals,
        ):
            raise ValueError("additional processing must use the accepted currency and precision")
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


class DataVerification(Contract):
    proposal: ProposalBinding
    specification_sha256: Digest
    evidence_sha256: Digest
    verified_at: AwareDatetime
    checks: Annotated[tuple[RequirementAssessment, ...], Field(min_length=1)]

    @property
    def verdict(self) -> Literal["PASS", "FAIL", "UNKNOWN"]:
        states = {check.verdict for check in self.checks}
        return "FAIL" if "FAIL" in states else "UNKNOWN" if "UNKNOWN" in states else "PASS"


class AcceptedDataAmendment(Contract):
    amendment_id: Text
    effective_at: AwareDatetime
    specification: DataSpecification
    accepted_by_customer: Text
    accepted_by_provider: Text


class InvestigationInput(Contract):
    case_id: Text
    snapshot: OrderSnapshot
    delivery: DeliveryVersion
    proposal: ProposalBinding
    complaint: Text | None = None
    evidence: Annotated[tuple[EvidenceReference, ...], Field(min_length=1)]
    free_regenerations_used: Annotated[StrictInt, Field(ge=0, le=1)] = 0
    questions_asked: Annotated[StrictInt, Field(ge=0, le=2)] = 0
    answers: tuple[CustomerAnswer, ...] = ()

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
        if len({answer.question_id for answer in self.answers}) != len(self.answers):
            raise ValueError("customer answers must refer to unique questions")
        if len(self.answers) > self.questions_asked or any(
            answer.evidence not in self.evidence or answer.evidence.kind != "customer_evidence"
            for answer in self.answers
        ):
            raise ValueError("customer answers must bind supplied evidence and the question budget")
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


class InvoiceCriterion(StrEnum):
    COMPLETE_COVERAGE = "complete_coverage"
    NO_DOUBLE_COUNTING = "no_double_counting"
    ACCURATE_EXTRACTION = "accurate_extraction"
    CORRECT_ARITHMETIC = "correct_arithmetic"
    TRACEABLE_EVIDENCE = "traceable_evidence"
    HONEST_UNCERTAINTY = "honest_uncertainty"
    CORRECT_FINAL_DELIVERY = "correct_final_delivery"
    DEFINED_SCOPE = "defined_scope"


class CriterionAssessment(Contract):
    criterion: InvoiceCriterion
    status: Literal["passed", "failed", "unknown"]
    explanation: Text
    citations: tuple[Citation, ...] = ()

    @model_validator(mode="after")
    def require_evidence(self) -> Self:
        if self.status != "unknown" and not self.citations:
            raise ValueError("passed/failed checks require cited evidence")
        return self


class InvestigationQuestion(Contract):
    question_id: Text
    prompt: Text
    missing_evidence: Text


class CustomerAnswer(Contract):
    question_id: Text
    text: Text
    evidence: EvidenceReference


InvestigationInput.model_rebuild()


class Recommendation(Contract):
    action: Literal[
        "capture", "additional_processing", "free_regeneration", "request_evidence", "human_review"
    ]
    rationale: Text


class InvestigationResult(Contract):
    case_id: Text
    proposal: ProposalBinding
    findings: tuple[Finding, ...]
    unresolved_issues: tuple[Text, ...]
    verdict: Literal["compliant", "provider_defect", "insufficient_evidence"]
    claim_assessment: Literal["not_applicable", "supported", "refuted", "unresolved"]
    checks: tuple[CriterionAssessment, ...]
    questions: Annotated[tuple[InvestigationQuestion, ...], Field(max_length=1)]
    recommendations: Annotated[tuple[Recommendation, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def check_verdict(self) -> Self:
        criteria = [check.criterion for check in self.checks]
        if len(set(criteria)) != len(criteria):
            raise ValueError("each invoice criterion may be assessed once")
        if self.verdict == "compliant":
            if set(criteria) != set(InvoiceCriterion) or any(
                check.status != "passed" for check in self.checks
            ):
                raise ValueError(
                    "compliant verdict requires evidence for all eight invoice criteria"
                )
            if self.questions or self.unresolved_issues:
                raise ValueError("compliant verdict cannot leave unanswered evidence gaps")
        if self.verdict == "provider_defect" and not any(
            check.status == "failed" for check in self.checks
        ):
            raise ValueError("provider defect requires a cited failed criterion")
        if self.verdict != "insufficient_evidence" and self.questions:
            raise ValueError("only an inconclusive review asks for missing evidence")
        return self

    def validate_for(self, request: InvestigationInput) -> None:
        """Runtime calls this before storing/using an untrusted investigator result."""
        if self.case_id != request.case_id or self.proposal != request.proposal:
            raise ValueError("stale or unrelated investigation result")
        allowed = {(item.evidence_id, item.version, item.sha256): item for item in request.evidence}
        if request.complaint is None:
            if self.claim_assessment != "not_applicable" or self.questions:
                raise ValueError("questions and claim assessments require a customer dispute")
        else:
            expected = {
                "compliant": "refuted",
                "provider_defect": "supported",
                "insufficient_evidence": "unresolved",
            }[self.verdict]
            if self.claim_assessment != expected:
                raise ValueError("claim assessment must match the evidence verdict")
        if request.questions_asked + len(self.questions) > request.snapshot.policy.max_questions:
            raise ValueError("two-question budget exhausted; escalate to human review")
        for finding in (*self.findings, *self.checks):
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
        for check in self.checks:
            if (
                check.criterion == InvoiceCriterion.CORRECT_FINAL_DELIVERY
                and check.status != "unknown"
            ):
                output_ids = {
                    item.evidence_id
                    for item in request.delivery.artifacts
                    if item.media_type == "application/pdf"
                }
                if not any(citation.evidence_id in output_ids for citation in check.citations):
                    raise ValueError("final delivery assessment must cite the actual delivered PDF")


class SettlementIntent(Contract):
    """Version-bound operation authorized by accepted policy and an evidence verdict/cutoff."""

    proposal: ProposalBinding
    action: Literal["capture", "release", "additional_processing"]
    amount: Money
    authorization_id: Text
    idempotency_key: Text


class OrderState(StrEnum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    FAILED = "failed"
    DELIVERED = "delivered"
    HUMAN_REVIEW = "human_review"
    CLOSED = "closed"


class DeliveryState(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    OPERATIONAL_FAILURE = "operational_failure"


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
