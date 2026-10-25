"""Audit regressions for repeated rows and mismatched raw model judgments."""

import copy
import json

import pytest

from connected_model_audit import verify_json_rows, verify_review_response


@pytest.mark.parametrize("duplicate", [False, True])
def test_json_rows_cannot_hide_duplicate_zip(duplicate):
    row = dict(zip="94110", area="Mission", count=123, status="released")
    rows = [row, row.copy()] if duplicate else [row]
    expected = {"94110": ("Mission", 123, "released")}
    if duplicate:
        with pytest.raises(AssertionError):
            verify_json_rows(rows, expected)
    else:
        verify_json_rows(rows, expected)


@pytest.mark.parametrize("mutation", [None, "result", "clause", "explanation", "missing"])
def test_complete_saved_review_matches_raw_provider_response(mutation):
    review = dict(
        result="UNKNOWN",
        clauses=[dict(text="A claim", result="UNKNOWN", citations=[], explanation="No evidence")],
        explanation="Evidence is missing",
    )
    response = dict(content=[dict(type="text", text=json.dumps(review))], stop_reason="end_turn")
    saved = copy.deepcopy(review)
    if mutation == "result":
        saved["result"] = "PASS"
    elif mutation == "clause":
        saved["clauses"][0]["text"] = "Different claim"
    elif mutation == "explanation":
        saved["explanation"] = "Rewritten answer"
    elif mutation == "missing":
        saved = None
    if mutation:
        with pytest.raises(AssertionError):
            verify_review_response(response, saved)
    else:
        verify_review_response(response, saved)


def test_invalid_response_cannot_become_valid_saved_review():
    response = dict(content=[dict(type="text", text="not JSON")], stop_reason="end_turn")
    verify_review_response(response, None)
    with pytest.raises(AssertionError):
        verify_review_response(response, {"result": "PASS"})


def test_incomplete_response_cannot_become_saved_review():
    review = dict(
        result="UNKNOWN",
        clauses=[dict(text="Claim", result="UNKNOWN", citations=[], explanation="Missing")],
        explanation="Missing evidence",
    )
    response = dict(content=[dict(type="text", text=json.dumps(review))], stop_reason="max_tokens")
    verify_review_response(response, None)
    with pytest.raises(AssertionError):
        verify_review_response(response, review)
