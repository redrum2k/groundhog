"""One prospective catalog procedure operation; no contractual or financial edits."""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.catalog import OrderCommand
from app.contracts.models import Contract, Text


class CatalogAcquisitionEdit(Contract):
    op: Literal["retrieve_registered_same_edition"]
    trigger: Literal["REQUIRED_VALUE_UNREADABLE"]


class CatalogPatchProposal(Contract):
    corpus_id: Text
    baseline_version: Text
    incident_ids: Annotated[tuple[Text, ...], Field(min_length=1, max_length=8)]
    rationale: Annotated[str, Field(min_length=1, max_length=1600)]
    expected_mechanism: Annotated[str, Field(min_length=1, max_length=1600)]
    operations: Annotated[tuple[CatalogAcquisitionEdit, ...], Field(min_length=1, max_length=1)]


class CatalogProposalBundle(Contract):
    candidates: Annotated[tuple[CatalogPatchProposal, ...], Field(max_length=2)]
    retain_base_reason: str | None = None


class CatalogImprovementCommand(Contract):
    idempotency_key: Text
    corpus_id: Text
    verb: Literal["propose", "probe", "approve", "activate", "revoke"]
    expected_active_version: Text
    incident_ids: Annotated[tuple[Text, ...], Field(max_length=8)] = ()
    patch_id: str | None = None
    probe_id: str | None = None
    version_id: str | None = None
    reason: Annotated[str, Field(min_length=1, max_length=1600)]
    mode: Literal["ANTHROPIC", "DETERMINISTIC_INFRASTRUCTURE"] = "ANTHROPIC"
    cycle: Literal[1, 2] = 1


class CatalogImprovementRecord(Contract):
    id: Text
    kind: Text
    corpus_id: Text
    # Raw model/probe evidence is intentionally lossless. Typed proposals/commands
    # are validated separately; this dictionary is evidence, never executable data.
    data: dict[str, Any]


class CatalogImprovementView(Contract):
    corpus_id: Text
    active_version: Text
    records: tuple[CatalogImprovementRecord, ...]
    statuses: dict[str, str]
    model_generation: Literal["CONFIGURED", "NOT_CONFIGURED"]
    local_demo_no_tenant_auth: Literal[True] = True


class CatalogImprovementResult(Contract):
    status: Literal[
        "COMPLETE", "FAILED", "UNKNOWN", "NOT_QUALIFIED", "APPROVED", "ACTIVE", "REVOKED"
    ]
    job_id: str | None = None
    patch_ids: tuple[str, ...] = ()
    probe_id: str | None = None
    version_id: str | None = None
    reason: str | None = None
    mode: str | None = None


class CatalogImprovementContractExport(Contract):
    command: CatalogImprovementCommand
    observe_command: OrderCommand
    proposal: CatalogPatchProposal
    bundle: CatalogProposalBundle
    view: CatalogImprovementView
    result: CatalogImprovementResult
