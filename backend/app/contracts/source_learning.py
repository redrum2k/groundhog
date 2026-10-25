"""Controlled local learning commands. No financial or executable-code fields."""

from typing import Annotated, Literal

from pydantic import Field

from app.agents.source_knowledge import AuthorityHead, VendorExport
from app.contracts.data_product import Frozen


class PartitionInput(Frozen):
    export: VendorExport
    authority: AuthorityHead


class BundleUpload(Frozen):
    idempotency_key: str = Field(min_length=1, max_length=160)
    origin: Literal["simulated_source_owner_demo"] = "simulated_source_owner_demo"
    partitions: Annotated[tuple[PartitionInput, ...], Field(min_length=2, max_length=4)]


class ResolveSource(Frozen):
    idempotency_key: str = Field(min_length=1, max_length=160)
    encounter_id: str
    column: str = Field(min_length=1, max_length=31)
    explanation: str = Field(min_length=1, max_length=1000)
    applicability: Literal["source_edition"] = "source_edition"


class LearningCommand(Frozen):
    idempotency_key: str = Field(min_length=1, max_length=160)
    target_id: str


class LearningResult(Frozen):
    status: str
    record_id: str
    detail: str = ""


class ReviewView(Frozen):
    encounter_id: str
    request_id: str
    source_family: str
    source_sha256: str
    authority_sha256: str
    reason: str
    columns: tuple[str, ...]
    resolved: bool


class CandidateView(Frozen):
    id: str
    component_ids: tuple[str, ...]
    status: str


class LearningEvent(Frozen):
    id: str
    request_id: str | None = None
    kind: str
    text: str
    actor: str
    created_at: str
    evidence_ids: tuple[str, ...] = ()


class QualificationView(Frozen):
    id: str
    candidate_id: str
    passed: bool
    cases: int
    baseline_reviews: int
    candidate_reviews: int
    baseline_operations: int
    candidate_operations: int
    correct_both: int
    capsule_sha256: str
    violations: tuple[str, ...]


class AttemptView(Frozen):
    id: str
    request_id: str
    active_version: str | None
    internal_reviews: int
    machine_operations: int
    baseline_reviews: int | None = None
    baseline_operations: int | None = None
    source_hashes: tuple[str, ...] = ()


class LearningState(Frozen):
    enabled: bool
    mode: Literal["controlled_local_mock"] = "controlled_local_mock"
    disclosure: str = (
        "Synthetic sources and simulated owner/controller identities; mock funding only."
    )
    active_version: str | None = None
    active_current: bool = False
    bundle_id: str | None = None
    reviews: tuple[ReviewView, ...] = ()
    candidates: tuple[CandidateView, ...] = ()
    versions: tuple[CandidateView, ...] = ()
    attempts: tuple[AttemptView, ...] = ()
    events: tuple[LearningEvent, ...] = ()
    qualification: QualificationView | None = None


class SourceLearningContractExport(Frozen):
    state: LearningState
    upload: BundleUpload
    resolution: ResolveSource
    command: LearningCommand
    result: LearningResult
