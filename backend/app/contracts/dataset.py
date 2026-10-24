"""Aggregate brokerage v1, distinct from the accepted regional broker v0.3 profile.

Reuse that profile's immutable source pins and provenance vocabulary. Cohort age,
integer suppression, authoritative coverage and CSV/preview agreement are new rules.
"""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, TypeAdapter, model_validator

from app.contracts.data_product import Frozen, Hash, Name, SourcePin, TermProvenance

DATASET_POLICY = "aggregate-brokerage-v1"
DATASET_CORPUS = "sf-aggregate-v1"
DATASET_COLUMNS = ("zip", "area", "count", "status")
DATASET_CHECKS = (
    "cohort",
    "category",
    "geography",
    "schema",
    "coverage",
    "suppression",
    "provenance",
    "artifact",
)
DatasetField = Literal[
    "cohort", "category", "geography", "schema", "coverage", "suppression", "provenance", "artifact"
]


class DatasetComplaintTarget(Frozen):
    requirement_id: Name
    field: DatasetField
    row_ids: tuple[Name, ...]
    columns: tuple[Literal["zip", "area", "count", "status"], ...]


class CoverageUniverse(Frozen):
    pin: SourcePin
    geography: Literal["San Francisco", "Oakland"]
    expected_keys: Annotated[tuple[Name, ...], Field(min_length=1, max_length=100)]
    authority_record: Name
    boundary_notice: str = "Synthetic ZIP inclusion registry; postal ZIPs are not city boundaries."

    @model_validator(mode="after")
    def unique_keys(self):
        if len(self.expected_keys) != len(set(self.expected_keys)):
            raise ValueError("coverage keys must be unique")
        return self


class DatasetSpecification(Frozen):
    domain: Literal["aggregate_dataset"] = "aggregate_dataset"
    policy_version: Literal["aggregate-brokerage-v1"] = DATASET_POLICY
    corpus_id: Name = DATASET_CORPUS
    geography: Literal["San Francisco", "Oakland"] = "San Francisco"
    age_min: Literal[25] = 25
    age_max: Literal[34] = 34
    category: Literal["gym_or_fitness_app", "gym_app_or_yoga"] = "gym_or_fitness_app"
    category_meaning: str = (
        "Gym membership or fitness-app use; yoga alone requires accepted taxonomy evidence."
    )
    population: Literal["synthetic_adults"] = "synthetic_adults"
    count_unit: Literal["unique_adults_per_zip"] = "unique_adults_per_zip"
    groups_disjoint: Literal[True] = True
    grouping: Literal["zip"] = "zip"
    required_columns: tuple[Literal["zip", "area", "count", "status"], ...] = DATASET_COLUMNS
    completeness: Literal["every_registry_key_once"] = "every_registry_key_once"
    suppression_threshold: Literal[50] = 50
    suppressed_count: None = None
    coverage: CoverageUniverse
    sources: Annotated[tuple[SourcePin, ...], Field(min_length=1, max_length=8)]
    provenance: tuple[TermProvenance, ...] = ()

    @model_validator(mode="after")
    def exact_contract(self):
        if self.required_columns != DATASET_COLUMNS:
            raise ValueError("all dataset columns in their specified order are mandatory")
        if self.coverage.geography != self.geography:
            raise ValueError("coverage geography must match the accepted cohort")
        if len({p.source_id for p in self.sources}) != len(self.sources):
            raise ValueError("one frozen edition per source")
        return self


class BrokeragePolicy(Frozen):
    version: Literal["aggregate-brokerage-v1"] = DATASET_POLICY
    pricing_version: Literal["datumco-demo-pricing-v1"] = "datumco-demo-pricing-v1"
    review_seconds: Literal[60] = 60
    dispute_seconds: Literal[60] = 60
    evidence_repair_seconds: Literal[120] = 120
    evidence_attempts: Literal[2] = 2
    max_questions: Literal[2] = 2
    free_corrections: Literal[1] = 1
    authorization_seconds: Literal[3600] = 3600
    clarification_seconds: Literal[300] = 300
    clarification_rounds: Literal[2] = 2
    scheduling_version: Literal["broker-budget-v1"] = "broker-budget-v1"
    fulfillment_seconds: Literal[135] = 135  # Three existing 45-second worker leases.
    correction_seconds: Literal[135] = 135
    transaction_margin_seconds: Literal[120] = 120


class DatasetRow(Frozen):
    zip: Annotated[str, Field(pattern=r"^\d{5}$")]
    area: Name
    count: Annotated[StrictInt, Field(ge=0)] | None
    status: Literal["released", "suppressed", "unknown"]

    @model_validator(mode="after")
    def safe_count(self):
        if self.status == "released" and (self.count is None or self.count < 50):
            raise ValueError("released counts must be integers at least 50")
        if self.status != "released" and self.count is not None:
            raise ValueError("suppressed and unknown counts must be null")
        return self


class DatasetReference(Frozen):
    kind: Literal["dataset"] = "dataset"
    artifact_id: Name
    sha256: Hash
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    row: Name
    column: Name
    value: str | None
    # Absence is grounded in both the checked artifact and the frozen denominator.
    expected_key: Name | None = None
    coverage_sha256: Hash | None = None


class DatasetSource(Frozen):
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)] = 1
    edition: Name
    geography: str
    age_min: StrictInt
    age_max: StrictInt
    category: str
    population: str
    count_unit: str
    groups_disjoint: bool
    rows: Annotated[tuple[DatasetRow, ...], Field(max_length=100)]


class DatasetManifest(Frozen):
    schema_version: Literal["aggregate-csv-v1"] = "aggregate-csv-v1"
    columns: tuple[str, ...] = DATASET_COLUMNS
    csv_sha256: Hash
    specification_sha256: Hash
    sources: tuple[SourcePin, ...]
    coverage: SourcePin
    rows: tuple[DatasetRow, ...]


class CoverageRow(Frozen):
    zip: Annotated[str, Field(pattern=r"^\d{5}$")]
    area: Name


class CoverageSource(Frozen):
    kind: Literal["coverage"]
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    geography: Literal["San Francisco", "Oakland"]
    authority_record: Name
    boundary_notice: str
    rows: Annotated[tuple[CoverageRow, ...], Field(min_length=1, max_length=100)]


class AuthoritySource(Frozen):
    kind: Literal["authority"]
    source_id: Name
    version: Annotated[StrictInt, Field(ge=1)]
    authority_record: Name
    registered_publisher: Name
    definition: str
    yoga_is_gym: StrictBool | None
    yoga_category: Name
    notice: str


# Each schema forbids extra fields. No discriminator's absence enables a raw fallback.
PUBLIC_DATASET_JSON = TypeAdapter(
    DatasetSource | DatasetManifest | CoverageSource | AuthoritySource
)
