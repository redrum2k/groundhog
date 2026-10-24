"""Versioned aggregate adapter to Jeff's bounded semantic assessor interface."""

import json

from app.agents.gateway import EvidencePassage, OfflineAssessor
from app.contracts.catalog import Assessment, Obligation, Provenance
from app.datasets import reference
from app.orders.dataset_evidence import answer_references


def investigate_dataset(order, report, store, assessor):
    case = order.cases[-1]
    terms = order.snapshot.quote.specification.terms
    authority = next(s for s in order.sources if s.source_id.endswith(":authority"))
    raw = json.loads(store.read(authority.artifact))
    refs = (
        reference(
            authority.artifact,
            authority.source_id,
            column="definition",
            value=raw.get("definition"),
        ),
        reference(
            authority.artifact,
            authority.source_id,
            column="yoga_is_gym",
            value=str(raw["yoga_is_gym"]).lower() if raw.get("yoga_is_gym") is not None else None,
        ),
    )
    for ref in refs:
        store.resolve(ref, order.artifacts)
    obligation = Obligation(
        obligation_id=f"{case.case_id}:claim",
        requirement_id=case.complaint.requirement_id,
        subject=case.complaint.product_id,
        field=case.complaint.field,
        check="dataset_semantic_claim",
        mandatory=False,
        decision_effect="remedy",
    )
    result, explanation = (
        "UNKNOWN",
        "The accepted definition and source meaning do not establish this claim.",
    )
    if isinstance(assessor, OfflineAssessor):
        if (
            case.complaint.field in ("coverage", "completeness")
            and case.complaint.product_id in terms.coverage.expected_keys
            and report.passed
        ):
            result, explanation = (
                "FAIL",
                "The exact disputed ZIP is present in the independently checked delivery.",
            )
            refs = (
                reference(
                    order.deliveries[-1].csv,
                    "delivery",
                    row=case.complaint.product_id,
                    column="zip",
                    value=case.complaint.product_id,
                    version=order.deliveries[-1].version,
                ),
            )
        elif "yoga" in case.complaint.text.lower() and case.complaint.field == "category":
            if terms.category == "gym_app_or_yoga" and report.passed:
                result, explanation = (
                    "FAIL",
                    (
                        "Yoga is already included in the accepted definition and verified "
                        "source; no expansion fee is owed."
                    ),
                )
            elif raw.get("yoga_is_gym") is False:
                result, explanation = (
                    "FAIL",
                    (
                        "Accepted fitness means gyms/apps; the frozen taxonomy excludes "
                        "standalone yoga. Extra yoga work needs a separate offer and "
                        "buyer acceptance."
                    ),
                )
            elif raw.get("yoga_is_gym") is True:
                result, explanation = (
                    "PASS",
                    (
                        "The frozen authority states yoga satisfies gym membership; it is "
                        "already owed, not billable expansion."
                    ),
                )
        return Assessment(
            obligation_id=obligation.obligation_id,
            result=result,
            citations=refs,
            missing_facts=(
                "Registered evidence establishing yoga's meaning under the accepted definition.",
            )
            if result == "UNKNOWN"
            else (),
            reason_code="DATASET_SEMANTIC_" + result,
            explanation=explanation,
            requested_evidence=(
                "Which frozen authority record establishes whether yoga "
                "membership satisfies the accepted gym/app definition?"
            )
            if result == "UNKNOWN"
            else None,
            provenance=Provenance(
                kind="deterministic", assessor="offline-dataset-semantics", version="1"
            ),
        )
    refs = tuple(dict.fromkeys((*refs, *answer_references(order, store))))
    passages = tuple(
        EvidencePassage(citation=r, text=store.resolve(r, order.artifacts) or "Unknown")
        for r in refs
    )
    finding = assessor.assess_obligation(
        obligation,
        f"Accepted definition: {terms.category_meaning}. Claim: {case.complaint.text}. "
        f"Customer testimony: {case.answers}. Testimony is not source authority.",
        passages,
    )
    if finding.obligation_id != obligation.obligation_id or any(
        r not in refs for r in (*finding.citations, *finding.conflicting_evidence)
    ):
        raise ValueError("semantic result is outside the bounded cited evidence")
    return finding
