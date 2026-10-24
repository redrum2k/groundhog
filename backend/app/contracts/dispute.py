"""Model proposals and server validation are distinct; neither grants financial authority."""

from typing import Annotated, Literal

from pydantic import Field

from app.contracts.data_product import Frozen, Hash, Name
from app.contracts.models import ProposalBinding

Kind = Literal["justified", "not_justified", "unclear"]


class DisputeReference(Frozen):
    artifact_id: Name
    version: Annotated[int, Field(ge=1)]
    sha256: Hash
    locator: Annotated[str, Field(min_length=1, max_length=400)]
    value: Annotated[str, Field(max_length=1600)]


class DisputeCandidate(Frozen):
    kind: Kind
    reason: Annotated[str, Field(min_length=1, max_length=2400)]
    obligation_id: Name | None
    references: Annotated[tuple[DisputeReference, ...], Field(max_length=20)]
    missing_facts: Annotated[tuple[str, ...], Field(max_length=12)]
    conflicting_facts: Annotated[tuple[str, ...], Field(max_length=12)]


class DisputeBinding(Frozen):
    order_id: Name
    issue_id: Name
    broker_revision: int
    order_revision: int
    proposal: ProposalBinding
    accepted_specification_sha256: Hash
    effective_specification_sha256: Hash
    evidence_sha256: Hash
    snapshot_sha256: Hash


class DisputeValidation(Frozen):
    status: Literal["SUPPORTED", "ADVISORY", "INVALID", "FAILED", "STALE"]
    reasons: tuple[str, ...]


class DisputeDecision(Frozen):
    kind: Kind
    reason: str
    decided_by: Literal["model", "rules", "unresolved"]
    effect: Literal["RESERVE_CORRECTION", "NO_REMEDY", "HOLD"]


class DisputeEvent(Frozen):
    attempt_id: Name
    kind: Kind
    reason: str
    evidence_ids: tuple[str, ...]
    decided_by: Literal["model", "rules", "unresolved"]
    binding: DisputeBinding
    raw_candidate: DisputeCandidate | None
    validation: DisputeValidation
    effective_decision: DisputeDecision
    references: tuple[DisputeReference, ...]
