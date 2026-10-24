import pytest
from pydantic import ValidationError

from app.contracts.models import (
    Citation,
    Finding,
    InvestigationQuestion,
    InvestigationResult,
    PdfHighlight,
    Recommendation,
)


@pytest.fixture
def result(investigation_input):
    evidence = investigation_input.evidence[0]
    return InvestigationResult(
        case_id=investigation_input.case_id,
        proposal=investigation_input.proposal,
        findings=(
            Finding(
                statement="The input contains a record requiring inspection in the output.",
                citations=(
                    Citation(
                        evidence_id=evidence.evidence_id,
                        version=evidence.version,
                        sha256=evidence.sha256,
                        locator="page 1, first record",
                        highlights=(PdfHighlight(page_number=1, x0=0.1, y0=0.2, x1=0.7, y1=0.3),),
                    ),
                ),
            ),
        ),
        unresolved_issues=("Output inspection is still needed.",),
        verdict="insufficient_evidence",
        claim_assessment="unresolved",
        checks=(),
        questions=(
            InvestigationQuestion(
                question_id="q1",
                prompt="Which record is reported missing?",
                missing_evidence="Identity of the disputed record",
            ),
        ),
        recommendations=(
            Recommendation(action="human_review", rationale="Evidence is incomplete."),
        ),
    )


def test_cited_result_round_trip(investigation_input, result):
    parsed = InvestigationResult.model_validate_json(result.model_dump_json())
    parsed.validate_for(investigation_input)


@pytest.mark.parametrize("field", ["delivery_version", "evidence_version", "proposal_version"])
def test_stale_result_rejected(investigation_input, result, field):
    data = result.model_dump()
    data["proposal"][field] = 2
    stale = InvestigationResult.model_validate(data)
    with pytest.raises(ValueError, match="stale"):
        stale.validate_for(investigation_input)


@pytest.mark.parametrize(
    "field,value", [("evidence_id", "unknown"), ("version", 2), ("sha256", "f" * 64)]
)
def test_citations_bind_exact_supplied_evidence(investigation_input, result, field, value):
    data = result.model_dump()
    data["findings"][0]["citations"][0][field] = value
    invalid = InvestigationResult.model_validate(data)
    with pytest.raises(ValueError, match="exact evidence"):
        invalid.validate_for(investigation_input)


def test_findings_require_citations():
    with pytest.raises(ValidationError):
        Finding(statement="Uncited assertion", citations=())


def test_result_rejects_unbounded_payment_permissions(result):
    data = result.model_dump()
    data["payment_authorized"] = True
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(data)
    data = result.model_dump()
    data["recommendations"][0]["action"] = "unbounded_debit"
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(data)


def test_pdf_citation_requires_highlight(investigation_input, result):
    data = result.model_dump()
    data["findings"][0]["citations"][0]["highlights"] = ()
    without_highlight = InvestigationResult.model_validate(data)
    with pytest.raises(ValueError, match="linked evidence highlights"):
        without_highlight.validate_for(investigation_input)
