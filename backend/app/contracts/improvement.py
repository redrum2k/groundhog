"""The entire editable surface: prospective questions and approved validator bindings."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt

from app.contracts.data_product import Frozen, Name, Recipe, SourcePin
from app.contracts.jobflow import Event
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
    op: Literal["require_intake_field", "replace_question", "bind_validator"]
    field: IntakeField | None = None
    question: Annotated[str | None, Field(min_length=1, max_length=600)] = None
    recipe: Recipe | None = None
    parameters_from: tuple[IntakeField, ...] = ()


class IncidentOutcome(Frozen):
    id: Name
    incident_id: Name
    entity_id: Name
    customer_id: Name
    product_id: Name
    outcome: Literal["ACCEPTED_AFTER_CLARIFICATION", "EVIDENCE_RESOLVED"]
    company_staff_touches: int
    touch_basis: Literal["entity_cumulative"] = "entity_cumulative"
    measured_staff_seconds: float | None = None
    binding: ProposalBinding | None = None
    created_at: AwareDatetime


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
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE", "ANTHROPIC", "ANTHROPIC_TEST_DOUBLE"]
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
    tested_questions: dict[str, str] = Field(default_factory=dict)
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


class ScenarioRun(Frozen):
    case_id: Name
    arm: Literal["static", "memory_only", "evolving_process"]
    outcome: Literal[
        "PASS",
        "FAIL",
        "UNKNOWN",
        "DECLINED",
        "BLOCKED",
        "UNSUPPORTED",
        "OPERATIONAL_FAILURE",
        "ERROR",
        "TIMEOUT",
    ]
    accepted: bool
    completed: bool
    company_staff_touches: int
    measured_staff_seconds: float | None
    customer_answers: int
    required_review_tasks: int
    seller_rework_attempts: int
    model_calls: int
    input_tokens: int
    output_tokens: int
    financial_effects: int
    observed_answer_fidelity: bool
    experience_ids: tuple[str, ...]
    violations: tuple[str, ...]
    artifact_hashes: tuple[str, ...]
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE"]
    trace: tuple[Event, ...]
    trace_sha256: str
    elapsed_ms: int
    error: str | None = None
    specification_sha256: str | None = None
    payment_phase: str | None = None
    order_state: str | None = None


class ScenarioComparison(Frozen):
    case_id: Name
    arms: dict[Literal["static", "memory_only", "evolving_process"], ScenarioRun]


class ProbeSummary(Frozen):
    incoming: int
    accepted: int
    completed: int
    company_staff_touches: int
    required_review_tasks: int
    customer_answers: int
    seller_rework_attempts: int
    outcomes: dict[str, int]
    model_calls: int
    measured_staff_seconds: float | None
    dollar_savings: float | None


class ProbeRun(Frozen):
    id: Name
    patch_id: Name
    customer_id: Name
    product_id: Name
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE"]
    candidate_sha256: str
    manifest_sha256: str
    implementation_sha256: str
    template_sha256: str
    outcomes: tuple[ScenarioComparison, ...]
    summary: dict[Literal["static", "memory_only", "evolving_process"], ProbeSummary]
    violations: tuple[str, ...]
    improved: bool
    promotion_eligible: bool
    selection: Literal["RETAIN_TESTED_CANDIDATE", "RETAIN_BASE"]
    composition: str
    approval_touch_cost: int
    active_staff_seconds_measured: bool
    elapsed_ms: int
    execution_interface: Literal["in_process_application_commands"] = (
        "in_process_application_commands"
    )


class ImprovementCommandResult(Frozen):
    status: Literal[
        "BLOCKED", "COMPLETE", "FAILED", "UNKNOWN", "RUNNING", "APPROVED", "ACTIVE", "REVOKED"
    ]
    job_id: str | None = None
    reason: str | None = None
    patch_ids: tuple[str, ...] = ()
    rejection_ids: tuple[str, ...] = ()
    patch_id: str | None = None
    patch_status: Literal["VALIDATED", "REJECTED"] | None = None
    probe_id: str | None = None
    version_id: str | None = None
    active_version: str | None = None
    mode: Literal["DETERMINISTIC_INFRASTRUCTURE", "ANTHROPIC", "ANTHROPIC_TEST_DOUBLE"] | None = (
        None
    )
    experience_ids: tuple[str, ...] = ()
    model_calls: int = 0
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    usage_known: bool = True
    proposer_model: str | None = None
    summary: dict[str, ProbeSummary] | None = None
    violations: tuple[str, ...] = ()
    promotion_eligible: bool | None = None


class ImprovementContractExport(Frozen):
    command: ImprovementCommand
    command_result: ImprovementCommandResult
    incident: GreyAreaIncident
    incident_outcome: IncidentOutcome
    patch: ImprovementPatch
    probe: ProbeRun
    version: ImprovementVersion
    experience: ImprovementExperience
