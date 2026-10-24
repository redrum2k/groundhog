from typing import Protocol

from app.contracts.models import InvestigationInput, InvestigationResult


class Investigator(Protocol):
    async def investigate(self, request: InvestigationInput) -> InvestigationResult:
        """Return cited findings, unresolved issues, questions, and recommendations.

        A complete evidence-backed verdict can authorize early closure and policy-bound
        payments. The runtime validates citations, versions, amounts and authorization.
        No payment/storage credentials or evaluation keys are provided. Ask at most
        one targeted question per round, with a two-question total budget.
        Jeff owns implementation choices; this protocol does not prescribe a graph.
        """
        ...
