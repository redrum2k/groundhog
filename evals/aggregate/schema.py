"""Strict evaluator inputs and immutable, content-addressed run plans."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_VERSION = "explicit-scope-v1"
AUDIT_VERSION = "primary-cells-v1"
REQUIREMENTS = tuple(
    "R-" + key.upper()
    for key in (
        "cohort",
        "category",
        "geography",
        "schema",
        "coverage",
        "suppression",
        "provenance",
        "artifact",
    )
)
Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Verdict = Literal["PASS", "FAIL", "UNKNOWN", "CONFLICT"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Case(Strict):
    id: Name
    title: Annotated[str, Field(min_length=1, max_length=200)]
    classification: Literal["development", "held_out"]
    recipe: Literal[
        "conforming", "correction", "complaint", "additional_scope", "insufficient", "contradictory"
    ]
    checkpoints: list[Name]


class Cases(Strict):
    schema_version: Literal["aggregate-cases-v1"]
    cases: Annotated[list[Case], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique(self):
        unique([c.id for c in self.cases], "case IDs")
        for case in self.cases:
            unique(case.checkpoints, "checkpoint IDs")
            required = {
                "conforming": ["delivery", "settled"],
                "correction": ["initial", "corrected"],
                "complaint": ["delivery", "complaint"],
                "additional_scope": ["parent", "child"],
                "insufficient": ["source"],
                "contradictory": ["source"],
            }[case.recipe]
            if case.checkpoints != required:
                raise ValueError("checkpoint IDs must match the versioned recipe")
        return self


class Label(Strict):
    requirement_id: Name
    result: Verdict
    rationale: Annotated[str, Field(min_length=1, max_length=2000)]


class CheckpointExpectation(Strict):
    id: Name
    requirements: list[Label]
    action: Literal[
        "publish", "correct", "request_evidence", "escalate", "settle", "unsupported", "block"
    ]
    payment_state: Literal[
        "blocked_parent",
        "awaiting_signature",
        "funding_pending",
        "funded",
        "capture_pending",
        "captured",
        "void_pending",
        "voided",
        "uncertain",
        "failed",
        "expired_not_returned",
        "reorg_hold",
    ]
    booking_count: Annotated[int, Field(strict=True, ge=0, le=10)]
    artifact_result: Literal["valid", "invalid", "not_produced"]
    complaint_result: Verdict | None = None


class Expectation(Strict):
    case_id: Name
    classification: Literal["development", "held_out"]
    review_status: Literal["engineering", "rehan_reviewed"]
    reviewer: Annotated[str, Field(min_length=1, max_length=200)]
    review_rationale: Annotated[str, Field(min_length=1, max_length=2000)]
    checkpoints: list[CheckpointExpectation]


class Expectations(Strict):
    schema_version: Literal["aggregate-expectations-v1"]
    expectations: list[Expectation]


class Config(Strict):
    schema_version: Literal["aggregate-scoring-v1"] = "aggregate-scoring-v1"
    case_seconds: Annotated[float, Field(gt=0, le=120)] = 20
    max_steps: Annotated[int, Field(strict=True, ge=1, le=100)] = 30
    seed: Annotated[int, Field(strict=True, ge=0)] = 0
    mode: Literal["offline_mock"] = "offline_mock"
    fixture_version: Literal["explicit-scope-v1"] = FIXTURE_VERSION
    audit_version: Literal["primary-cells-v1"] = AUDIT_VERSION


def unique(values, name):
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {name}")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def load_inputs(case_path, expectation_path, selected=()):
    cases = Cases.model_validate_json(case_path.read_bytes()).cases
    expectations = (
        Expectations.model_validate_json(expectation_path.read_bytes()).expectations
        if expectation_path
        else []
    )
    if expectation_path:
        unique([e.case_id for e in expectations], "expectation case IDs")
        by_id = {e.case_id: e for e in expectations}
        if set(by_id) != {c.id for c in cases}:
            raise ValueError("expectation case IDs must exactly match the case file")
        for case in cases:
            expected = by_id[case.id]
            if expected.classification != case.classification:
                raise ValueError("expectation classification mismatch")
            unique([c.id for c in expected.checkpoints], "expectation checkpoint IDs")
            if {c.id for c in expected.checkpoints} != set(case.checkpoints):
                raise ValueError("missing or mismatched checkpoint IDs")
            for checkpoint in expected.checkpoints:
                ids = [r.requirement_id for r in checkpoint.requirements]
                unique(ids, "requirement IDs")
                if set(ids) != set(REQUIREMENTS):
                    raise ValueError("every accepted requirement needs exactly one label")
    unique(selected, "selected case IDs")
    if set(selected) - {c.id for c in cases}:
        raise ValueError("unknown selected case ID; use list")
    cases = [c for c in cases if not selected or c.id in selected]
    return cases, [e for e in expectations if e.case_id in {c.id for c in cases}]


def verify_freeze(path):
    envelope = json.loads(path.read_bytes())
    if digest(envelope["plan"]) != envelope["sha256"]:
        raise ValueError("frozen plan hash mismatch")
    return envelope
