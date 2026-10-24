import pytest
from pydantic import ValidationError

from app.contracts.models import InvestigationInput, InvestigationResult


def test_evidenced_compliance_covers_all_invoice_criteria(investigation_input, result_for):
    result = result_for(investigation_input)
    assert len(result.checks) == 8
    result.validate_for(investigation_input)


@pytest.mark.parametrize(
    "change", ["missing", "unknown", "failed", "uncited", "duplicate", "unresolved"]
)
def test_compliant_verdict_cannot_skip_evidence(investigation_input, result_for, change):
    data = result_for(investigation_input).model_dump(mode="json")
    if change == "missing":
        data["checks"].pop()
    elif change in ("unknown", "failed"):
        data["checks"][0]["status"] = change
    elif change == "uncited":
        data["checks"][0]["citations"] = []
    elif change == "duplicate":
        data["checks"].append(data["checks"][0])
    else:
        data["unresolved_issues"] = ["Source totals remain uncertain."]
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(data)


def test_intermediate_data_or_source_pdf_cannot_prove_final_delivery(
    investigation_input, result_for
):
    data = result_for(investigation_input).model_dump(mode="json")
    final = next(
        check for check in data["checks"] if check["criterion"] == "correct_final_delivery"
    )
    final["citations"] = data["checks"][0]["citations"]
    result = InvestigationResult.model_validate(data)
    with pytest.raises(ValueError, match="actual delivered PDF"):
        result.validate_for(investigation_input)


def test_supported_claim_needs_cited_failure(investigation_input, result_for):
    data = result_for(investigation_input, "provider_defect").model_dump(mode="json")
    for check in data["checks"]:
        check["status"] = "passed"
    with pytest.raises(ValidationError, match="cited failed criterion"):
        InvestigationResult.model_validate(data)


def test_claim_assessment_must_match_verdict(investigation_input, result_for):
    data = result_for(investigation_input).model_dump(mode="json")
    data["claim_assessment"] = "supported"
    with pytest.raises(ValueError, match="claim assessment"):
        InvestigationResult.model_validate(data).validate_for(investigation_input)


def test_one_question_per_round(investigation_input, result_for):
    data = result_for(investigation_input, "insufficient_evidence", ask=True).model_dump(
        mode="json"
    )
    data["questions"].append({**data["questions"][0], "question_id": "q2"})
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(data)


def test_question_budget_survives_input_roundtrip(investigation_input, result_for):
    data = investigation_input.model_dump()
    data["questions_asked"] = 2
    request = InvestigationInput.model_validate(data)
    result = result_for(request, "insufficient_evidence", ask=True)
    with pytest.raises(ValueError, match="budget exhausted"):
        result.validate_for(request)
