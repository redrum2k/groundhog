"""Versioned data-product terms. No evaluator truth or executable recipes."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

Name = Annotated[str, Field(min_length=1, max_length=160)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Verdict = Literal["PASS", "FAIL", "UNKNOWN"]
Dimension = Literal[
    "freshness",
    "geography",
    "reference_period",
    "metric",
    "entity_unit",
    "coverage",
    "source_lineage",
    "output_schema",
    "unsupported",
]
Recipe = Literal[
    "age_within_days",
    "region_version",
    "period_equals",
    "metric_equals",
    "unique_entity",
    "coverage_ids",
    "exact_sources",
    "market_schema_v1",
    "unsupported",
]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class SourcePin(Frozen):
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    sha256: Hash


class TermProvenance(Frozen):
    reference_id: Name
    origin: Literal[
        "original_intent", "customer_answer", "provider_confirmation", "accepted_source"
    ]
    actor_id: Name


class Parameters(Frozen):
    freshness_basis: Literal["observed_at", "published_at", "exported_at"] | None = None
    max_age_days: Annotated[StrictInt, Field(ge=0, le=36500)] | None = None
    as_of: AwareDatetime | None = None
    geography: Name | None = None
    boundary_version: Name | None = None
    region_ids: tuple[Name, ...] = ()
    reference_period: Name | None = None
    metric_name: Name | None = None
    metric_unit: Name | None = None
    entity_unit: (
        Literal["establishment", "legal_entity", "household", "person", "region"] | None
    ) = None
    coverage_ids: tuple[Name, ...] = ()
    max_missing_records: Annotated[StrictInt, Field(ge=0, le=1000)] | None = None
    output_schema: Literal["market-v1"] | None = None
    output_format: Literal["json", "csv"] | None = None
    revision_policy: Literal["exact_accepted_versions"] | None = None
    conflict_policy: Literal["UNKNOWN"] | None = None


class Requirement(Frozen):
    id: Name
    dimension: Dimension
    meaning: Annotated[str, Field(min_length=1, max_length=1200)]
    recipe: Recipe
    parameters: Parameters
    missing_policy: Literal["UNKNOWN"] = "UNKNOWN"
    conflict_policy: Literal["UNKNOWN"] = "UNKNOWN"
    provenance: tuple[TermProvenance, ...] = ()


class DataSpecification(Frozen):
    version: Annotated[StrictInt, Field(ge=1)] = 1
    product_id: Name = "aggregate_regional_market_intelligence"
    template_version: Name = "intake-v1"
    original_intent: Annotated[str, Field(min_length=1, max_length=8000)]
    requirements: Annotated[tuple[Requirement, ...], Field(min_length=1, max_length=32)]
    sources: Annotated[tuple[SourcePin, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def unique_requirements(self):
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError("requirement IDs must be unique")
        if len({r.dimension for r in self.requirements}) != len(self.requirements):
            raise ValueError("one explicit requirement per dimension")
        if len({s.source_id for s in self.sources}) != len(self.sources):
            raise ValueError("one accepted version per source ID")
        return self


class DataRow(Frozen):
    entity_id: Name
    region_id: Name
    value: Annotated[float, Field(allow_inf_nan=False)]
    observed_at: AwareDatetime | None = None


class SourceSnapshot(Frozen):
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    geography: Name
    boundary_version: Name
    reference_period: Name
    metric_name: Name
    metric_unit: Name
    entity_unit: Literal["establishment", "legal_entity", "household", "person", "region"]
    published_at: AwareDatetime | None = None
    exported_at: AwareDatetime | None = None
    rows: Annotated[tuple[DataRow, ...], Field(min_length=1, max_length=1000)]


class DataCitation(Frozen):
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    sha256: Hash
    locator: Annotated[str, Field(min_length=1, max_length=400)]
    value: Annotated[str, Field(max_length=1600)]


class RequirementAssessment(Frozen):
    requirement_id: Name
    verdict: Verdict
    cause: Literal[
        "NONE",
        "MISSING_SPECIFICATION",
        "MISSING_EVIDENCE",
        "CONFLICTING_AUTHORITY",
        "VALIDATOR_FAILURE",
        "PROVIDER_DEFECT",
        "SCOPE_CHANGE",
        "UNSUPPORTED_SUBJECTIVE",
    ]
    explanation: Annotated[str, Field(min_length=1, max_length=1600)]
    citations: tuple[DataCitation, ...] = ()

    @model_validator(mode="after")
    def evidence_for_decision(self):
        if self.verdict != "UNKNOWN" and not self.citations:
            raise ValueError("PASS/FAIL requires exact artifact evidence")
        return self
