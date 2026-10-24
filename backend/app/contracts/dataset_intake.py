"""Model intent proposals, never accepted terms or permission to broaden scope."""

from typing import Literal

from pydantic import Field

from app.contracts.models import Contract


class DatasetIntakeProposal(Contract):
    requested_scope: Literal[
        "gym_or_fitness_app",
        "gym_app_or_yoga",
        "gym_only",
        "app_only",
        "yoga_only",
        "ambiguous",
        "unsupported",
    ]
    evidence_quote: str = Field(min_length=1, max_length=1000)
    clarification_field: Literal["cohort", "category"] = "category"
    clarification: str | None = Field(default=None, max_length=500)
    explanation: str = Field(min_length=1, max_length=1000)
