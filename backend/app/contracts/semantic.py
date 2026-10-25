"""Audit data for the existing primary dataset assessor, not a second verdict store."""

from typing import Annotated, Literal

from pydantic import Field

from app.contracts.catalog import Assessment, Binding
from app.contracts.dataset import DatasetReference
from app.contracts.models import Contract, Text


class DatasetClauseReview(Contract):
    text: Text
    result: Literal["PASS", "FAIL", "UNKNOWN", "CONFLICT"]
    citations: tuple[DatasetReference, ...] = ()
    explanation: Text


class DatasetClaimReview(Contract):
    """A blind second model judgment, not a deterministic entailment certificate."""

    result: Literal["PASS", "FAIL", "UNKNOWN", "CONFLICT"]
    clauses: Annotated[tuple[DatasetClauseReview, ...], Field(min_length=1, max_length=8)]
    explanation: Text


class DatasetSemanticAttempt(Contract):
    attempt_id: str
    order_id: str
    case_id: str
    order_revision: int
    # Original assessment provenance is immutable; only a pure durable-job reclaim
    # may advance the revision at which this completed result can be applied.
    recovery_revisions: tuple[int, ...] = ()
    binding: Binding
    accepted_specification_sha256: str
    status: Literal["DISPATCHED", "VALIDATED", "ADVISORY", "INVALID", "FAILED", "STALE"]
    request: dict | None = None
    raw_response: dict | None = None
    review_request: dict | None = None
    review_response: dict | None = None
    review: DatasetClaimReview | None = None
    review_failure: str | None = None
    candidate: Assessment | None = None
    effective: Assessment | None = None
    failure: str | None = None
    elapsed_seconds: float | None = None

    @property
    def application_revision(self):
        return self.recovery_revisions[-1] if self.recovery_revisions else self.order_revision
