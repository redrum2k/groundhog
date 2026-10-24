from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.models import (
    AcceptedPolicy,
    Citation,
    CriterionAssessment,
    DeliveryVersion,
    EvidencePointer,
    EvidenceReference,
    InvestigationInput,
    InvestigationQuestion,
    InvestigationResult,
    InvoiceCriterion,
    Money,
    OrderSnapshot,
    PdfHighlight,
    ProposalBinding,
    Recommendation,
    SettlementIntent,
)


@pytest.fixture
def investigation_input():
    source = EvidenceReference(
        evidence_id="input-1",
        version=1,
        sha256="a" * 64,
        storage_key="orders/order-1/inputs/input-1/v1",
        media_type="application/pdf",
        kind="accepted_input",
    )
    artifact = EvidenceReference(
        evidence_id="output-1",
        version=1,
        sha256="b" * 64,
        storage_key="orders/order-1/deliveries/v1/output-1",
        media_type="application/pdf",
        kind="delivery_artifact",
    )
    structured = tuple(
        EvidenceReference(
            evidence_id=f"{reference.evidence_id}-records",
            version=1,
            sha256=digest * 64,
            storage_key=f"{reference.storage_key}/structured",
            media_type="application/json",
            kind="structured_data",
            derived_from=(
                EvidencePointer(
                    evidence_id=reference.evidence_id,
                    version=reference.version,
                    sha256=reference.sha256,
                ),
            ),
        )
        for reference, digest in ((source, "c"), (artifact, "d"))
    )
    accepted_at = datetime(2026, 10, 23, 12, tzinfo=UTC)
    snapshot = OrderSnapshot(
        order_id="order-1",
        snapshot_id="snapshot-1",
        accepted_at=accepted_at,
        accepted_brief="Preserve every input record in the output.",
        input_versions=(source,),
        structured_data=(structured[0],),
        price=Money(amount_minor=1000, currency="USD", decimals=2),
        policy=AcceptedPolicy(policy_version="invoice-v2"),
    )
    delivery = DeliveryVersion(
        order_id=snapshot.order_id,
        snapshot_id=snapshot.snapshot_id,
        version=1,
        delivered_at=accepted_at + timedelta(seconds=10),
        artifacts=(artifact,),
        structured_data=(structured[1],),
    )
    return InvestigationInput(
        case_id="case-1",
        snapshot=snapshot,
        delivery=delivery,
        proposal=ProposalBinding(
            order_id=snapshot.order_id,
            snapshot_id=snapshot.snapshot_id,
            delivery_version=1,
            evidence_version=1,
            proposal_version=1,
        ),
        complaint="An input record appears to be missing.",
        evidence=(source, artifact, *structured),
    )


@pytest.fixture
def capture_intent(investigation_input):
    return SettlementIntent(
        proposal=investigation_input.proposal,
        action="capture",
        amount=investigation_input.snapshot.price,
        authorization_id="authorization-1",
        idempotency_key="order-1-capture-v1",
    )


@pytest.fixture
def result_for():
    def build(request, verdict="compliant", *, ask=False):
        source = request.snapshot.input_versions[0]
        output = request.delivery.artifacts[0]

        def cite(reference):
            return Citation(
                evidence_id=reference.evidence_id,
                version=reference.version,
                sha256=reference.sha256,
                locator="page 1, invoice rows",
                highlights=(PdfHighlight(page_number=1, x0=0.1, y0=0.1, x1=0.8, y1=0.8),),
            )

        checks = tuple(
            CriterionAssessment(
                criterion=criterion,
                status=(
                    "unknown"
                    if verdict == "insufficient_evidence"
                    else "failed"
                    if verdict == "provider_defect"
                    and criterion == InvoiceCriterion.COMPLETE_COVERAGE
                    else "passed"
                ),
                explanation="Synthetic assessment for contract/workflow tests.",
                citations=()
                if verdict == "insufficient_evidence"
                else (
                    cite(
                        output if criterion == InvoiceCriterion.CORRECT_FINAL_DELIVERY else source
                    ),
                ),
            )
            for criterion in InvoiceCriterion
        )
        claim = (
            "not_applicable"
            if request.complaint is None
            else {
                "compliant": "refuted",
                "provider_defect": "supported",
                "insufficient_evidence": "unresolved",
            }[verdict]
        )
        return InvestigationResult(
            case_id=request.case_id,
            proposal=request.proposal,
            verdict=verdict,
            claim_assessment=claim,
            checks=checks,
            findings=(),
            unresolved_issues=("Missing evidence",) if verdict == "insufficient_evidence" else (),
            questions=(
                InvestigationQuestion(
                    question_id=f"q{request.questions_asked + 1}",
                    prompt="Which source supports your claim?",
                    missing_evidence="Disputed invoice source",
                ),
            )
            if ask
            else (),
            recommendations=(
                Recommendation(
                    action={
                        "compliant": "capture",
                        "provider_defect": "free_regeneration",
                        "insufficient_evidence": "request_evidence" if ask else "human_review",
                    }[verdict],
                    rationale="Based on the cited checks.",
                ),
            ),
        )

    return build


from tests.catalog.fixtures import setup  # noqa: E402, F401


@pytest.fixture(autouse=True)
def disable_paid_calls(monkeypatch):
    """A developer's optional local Claude settings must never turn tests into paid calls."""
    monkeypatch.setenv("ENABLE_PAID_MODELS", "false")
