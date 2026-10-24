import json

import pytest
from pydantic import ValidationError

from app.contracts.models import (
    AcceptedPolicy,
    InvestigationInput,
    Money,
    OrderSnapshot,
    PdfHighlight,
    ProposalBinding,
    SettlementIntent,
)


@pytest.mark.parametrize("amount", [True, False, 1.0, 1.5, "1000", 0, -1])
def test_money_requires_positive_integer_minor_units(amount):
    with pytest.raises(ValidationError):
        Money.model_validate_json(
            json.dumps({"amount_minor": amount, "currency": "USD", "decimals": 2})
        )


def test_snapshot_is_frozen_and_round_trips(investigation_input):
    snapshot = investigation_input.snapshot
    assert OrderSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    with pytest.raises(ValidationError):
        snapshot.accepted_brief = "changed"
    with pytest.raises(ValidationError):
        snapshot.price.amount_minor = 1
    assert isinstance(snapshot.input_versions, tuple)


@pytest.mark.parametrize("field,value", [("review_window_seconds", 61), ("free_regenerations", 2)])
def test_confirmed_policy_is_fixed(field, value):
    with pytest.raises(ValidationError):
        AcceptedPolicy(policy_version="v1", **{field: value})


@pytest.mark.parametrize("value", [True, 1.0, "1", 0, -1])
def test_versions_are_positive_integers(investigation_input, value):
    data = investigation_input.proposal.model_dump()
    data["evidence_version"] = value
    with pytest.raises(ValidationError):
        ProposalBinding.model_validate(data)


@pytest.mark.parametrize(
    "field,value", [("order_id", "other"), ("snapshot_id", "other"), ("delivery_version", 2)]
)
def test_investigation_rejects_mixed_versions(investigation_input, field, value):
    data = investigation_input.model_dump()
    data["proposal"][field] = value
    with pytest.raises(ValidationError, match="exact delivery"):
        InvestigationInput.model_validate(data)


def test_evidence_must_include_exact_frozen_inputs(investigation_input):
    data = investigation_input.model_dump()
    data["evidence"][0]["sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="exact accepted inputs"):
        InvestigationInput.model_validate(data)


def test_evidence_cannot_contain_two_versions_of_same_item(investigation_input):
    data = investigation_input.model_dump()
    data["evidence"] = (*data["evidence"], {**data["evidence"][0], "version": 2})
    with pytest.raises(ValidationError, match="one version per"):
        InvestigationInput.model_validate(data)


def test_naive_timestamps_are_rejected(investigation_input):
    data = investigation_input.snapshot.model_dump()
    data["accepted_at"] = "2026-10-23T12:00:00"
    with pytest.raises(ValidationError):
        OrderSnapshot.model_validate(data)


def test_answer_keys_are_not_an_input_field(investigation_input):
    data = investigation_input.model_dump()
    data["expected_answer"] = "evaluation only"
    with pytest.raises(ValidationError, match="Extra inputs"):
        InvestigationInput.model_validate(data)


def test_no_additional_debit_operation(capture_intent):
    data = capture_intent.model_dump()
    data["action"] = "additional_debit"
    with pytest.raises(ValidationError):
        SettlementIntent.model_validate(data)


@pytest.mark.parametrize(
    "changes",
    [
        {"page_number": 0},
        {"page_number": True},
        {"x0": -0.1},
        {"x1": 1.1},
        {"x1": 0.1},
        {"y1": 0.1},
        {"x0": float("nan")},
        {"y1": float("inf")},
    ],
)
def test_pdf_highlights_have_valid_pages_and_normalized_rectangles(changes):
    data = {"page_number": 1, "x0": 0.1, "y0": 0.2, "x1": 0.8, "y1": 0.4, **changes}
    with pytest.raises(ValidationError):
        PdfHighlight.model_validate(data)


def test_structured_data_preserves_exact_source_provenance(investigation_input):
    data = investigation_input.snapshot.model_dump()
    data["structured_data"][0]["derived_from"][0]["version"] = 2
    with pytest.raises(ValidationError, match="exact source artifact versions"):
        OrderSnapshot.model_validate(data)


def test_structured_data_requires_provenance(investigation_input):
    data = investigation_input.snapshot.model_dump()
    data["structured_data"][0]["derived_from"] = ()
    with pytest.raises(ValidationError, match="exact source evidence"):
        OrderSnapshot.model_validate(data)


def test_investigator_receives_retained_structured_data(investigation_input):
    data = investigation_input.model_dump()
    data["evidence"] = data["evidence"][:2]
    with pytest.raises(ValidationError, match="exact accepted inputs"):
        InvestigationInput.model_validate(data)
