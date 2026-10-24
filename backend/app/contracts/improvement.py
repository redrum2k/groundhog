"""The entire editable surface: prospective questions and approved validator bindings."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt

from app.contracts.data_product import Frozen, Name, Recipe, SourcePin
from app.contracts.models import ProposalBinding

IntakeField = Literal[
    "freshness_basis",
    "max_age_days",
    "as_of",
    "geography",
    "boundary_version",
    "region_ids",
    "reference_period",
    "metric_name",
    "metric_unit",
    "entity_unit",
    "coverage_ids",
    "max_missing_records",
    "revision_policy",
    "conflict_policy",
    "output_schema",
    "output_format",
]


class GreyAreaIncident(Frozen):
    id: Name
    entity_id: Name
    issue_id: str | None = None
    customer_id: Name
    product_id: Name
    template_version: Name
    specification_sha256: str | None = None
    binding: ProposalBinding | None = None
    cause: Literal[
        "MISSING_SPECIFICATION",
        "MISSING_EVIDENCE",
        "CONFLICTING_AUTHORITY",
        "VALIDATOR_FAILURE",
        "SCOPE_CHANGE",
        "UNSUPPORTED_SUBJECTIVE",
        "REPEATED_INTERVENTION",
    ]
    material_unknowns: tuple[str, ...]
    questions: tuple[str, ...] = ()
    sources: tuple[SourcePin, ...] = ()
    outcome: str
    company_staff_touches: Annotated[StrictInt, Field(ge=0)] = 0
    measured_staff_seconds: Annotated[float, Field(ge=0)] | None = None
    created_at: AwareDatetime


class PatchEdit(Frozen):
    op: Literal["require_intake_field", "replace_question", "request_provenance", "bind_validator"]
    field: IntakeField | None = None
    question: Annotated[str | None, Field(min_length=1, max_length=600)] = None
    recipe: Recipe | None = None
    parameters_from: tuple[IntakeField, ...] = ()


class PatchProposal(Frozen):
    baseline_version: Name
    customer_id: Name
    product_id: Name
    incident_ids: Annotated[tuple[Name, ...], Field(min_length=1, max_length=8)]
    rationale: Annotated[str, Field(min_length=1, max_length=1600)]
    expected_mechanism: Annotated[str, Field(min_length=1, max_length=1600)]
    operations: Annotated[tuple[PatchEdit, ...], Field(min_length=1, max_length=8)]
    experience_ids: tuple[Name, ...] = ()


class ImprovementPatch(Frozen):
    id: Name
    cycle_id: Name
    proposal: PatchProposal
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE", "ANTHROPIC"]
    proposer_model: str | None = None
    input_tokens: Annotated[StrictInt, Field(ge=0)] = 0
    output_tokens: Annotated[StrictInt, Field(ge=0)] = 0
    created_at: AwareDatetime


class ImprovementVersion(Frozen):
    id: Name
    customer_id: Name
    product_id: Name
    previous_version: Name
    required_fields: tuple[IntakeField, ...]
    questions: dict[str, str] = Field(default_factory=dict)
    provenance_fields: tuple[IntakeField, ...] = ()
    validators: tuple[Recipe, ...] = ()
    patch_ids: tuple[Name, ...]
    probe_ids: tuple[Name, ...]
    approved_by: Name
    approved_at: AwareDatetime


class ImprovementExperience(Frozen):
    id: Name
    customer_id: Name
    product_id: Name
    cue: str
    attempted_change: tuple[PatchEdit, ...]
    observed_contrast: str
    lesson: str
    rejection_reason: str | None = None
    probe_ids: tuple[Name, ...]
    patch_id: Name
    created_at: AwareDatetime


class ImprovementCommand(Frozen):
    idempotency_key: Name
    verb: Literal["propose", "probe", "approve", "activate", "revoke"]
    customer_id: Name
    product_id: Name = "aggregate_regional_market_intelligence"
    incident_ids: tuple[Name, ...] = ()
    patch_id: str | None = None
    version_id: str | None = None
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE", "ANTHROPIC"] = "ANTHROPIC"
