from typing import Protocol

from app.contracts.models import InvestigationInput, InvestigationResult


class Investigator(Protocol):
    async def investigate(self, request: InvestigationInput) -> InvestigationResult:
        """Return cited findings, unresolved issues, questions, and recommendations.

        No payment/storage credentials or evaluation keys are provided. The runtime
        validates the result against this input and the latest persisted versions.
        Jeff owns implementation choices; this protocol does not prescribe a graph.
        """
        ...
