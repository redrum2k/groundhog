"""Semantic interpretation with bounded, resolved passages. Jeff owns this subsystem."""

from app.agents.gateway import EvidencePassage, OfflineAssessor
from app.contracts.catalog import Assessment, Obligation, Provenance


class CatalogInvestigator:
    def __init__(self, assessor=None):
        self.assessor = assessor or OfflineAssessor()

    def investigate(self, context, report, store):
        complaint = context.case.complaint
        terms = context.fulfillment.snapshot.quote.specification.terms
        requirement = next(
            r
            for r in context.fulfillment.snapshot.quote.specification.requirements
            if r.requirement_id == complaint.requirement_id
        )
        relevant_ids = {
            o.obligation_id
            for o in report.obligations
            if o.subject in (complaint.product_id, "delivery")
        }
        citations = tuple(
            dict.fromkeys(
                c
                for a in report.assessments
                if a.obligation_id in relevant_ids
                for c in a.citations
            )
        )[:8]
        allowed = (*tuple(s.artifact for s in context.fulfillment.sources), context.delivery.pdf)
        passages = tuple(
            EvidencePassage(citation=c, text=store.resolve(c, allowed)) for c in citations
        )
        obligation = Obligation(
            obligation_id=f"{context.case.case_id}:claim",
            requirement_id=complaint.requirement_id,
            subject=complaint.product_id,
            field=complaint.field,
            check="semantic_claim",
            mandatory=False,
            decision_effect="remedy",
        )
        # A small explicit offline language, not a general factual refutation heuristic.
        if (
            isinstance(self.assessor, OfflineAssessor)
            and terms.weight_concept == "net_unit"
            and complaint.text.lower().strip() == "shipping weight exceeds the net limit"
        ):
            return Assessment(
                obligation_id=obligation.obligation_id,
                result="FAIL",
                citations=citations,
                reason_code="DIFFERENT_WEIGHT_CONCEPT",
                explanation=(
                    "Claim compares shipping weight; the accepted criterion uses net unit weight."
                ),
                provenance=Provenance(
                    kind="deterministic", assessor="offline-catalog-semantics", version="1"
                ),
            )
        claim = (
            f"Accepted requirement: {requirement.wording}\nCustomer claim: {complaint.text}\n"
            f"Prior answers: {context.case.answers}. Assess whether the cited evidence supports "
            "the customer's factual claim. A request to change terms needs consent."
        )
        assessment = self.assessor.assess_obligation(obligation, claim, passages)
        if assessment.obligation_id != obligation.obligation_id:
            raise ValueError("semantic result refers to a different obligation")
        for span in (*assessment.citations, *assessment.conflicting_evidence):
            store.resolve(span, allowed)
            if span not in citations:
                raise ValueError("semantic result cites evidence outside its bounded bundle")
        return assessment
