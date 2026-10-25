"""Attributed reviewer reference material, separate from findings and payment authority."""

from typing import Annotated

from pydantic import AwareDatetime, Field

from app.contracts.catalog import Binding
from app.contracts.data_product import Frozen
from app.contracts.dataset import DatasetReference


class GuidanceConsulted(Frozen):
    memory_id: str
    actor: str
    originating_order: str
    originating_case: str
    explanation: str
    guidance: str
    applicability: dict
    current_citations: Annotated[tuple[DatasetReference, ...], Field(max_length=8)]


class ReviewerMemory(Frozen):
    memory_id: str
    decision_id: str
    actor: str
    originating_order: str
    originating_case: str
    originating_run: str
    binding: Binding
    recorded_at: AwareDatetime
    explanation: str
    guidance: str
    applicability: dict
    compatibility_key: str
    cited_evidence: Annotated[tuple[DatasetReference, ...], Field(min_length=1, max_length=8)]
