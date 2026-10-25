import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.roi.economics import normalized, project
from evals.roi.ledger import Ledger, unique_episodes
from evals.roi.plan import ARMS, digest, make_plan


def test_manifest_is_frozen_reproducible_and_expectations_separate():
    plan, expected = make_plan()
    assert make_plan() == (plan, expected)
    assert len(plan["cases"]) == 60 and len(plan["setup"]) == 7
    assert plan["counts"] == dict(
        repeat=20, documented=10, defect=8, objection=8, scope=6, exception=8
    )
    assert set(ARMS) == set(plan["arms"])
    assert all("expected" not in case and "disposition" not in case for case in plan["cases"])
    assert len(expected) == 67
    assert len({digest(c["source"]) for c in plan["cases"]}) == 60
    same_claim = [c for c in plan["cases"] if c.get("complaint") == "Does standalone yoga count?"]
    assert {expected[c["case_id"]]["semantic"] for c in same_claim} == {"PASS", "FAIL"}


def test_retries_and_repeated_displays_do_not_create_more_work():
    case = make_plan()[0]["cases"][0]
    ledger = Ledger(case, "operator", digest(case))
    for _ in range(4):
        ledger.add("operator", "final_review", "same-request")
    events = list(ledger.events.values())
    assert len(events) == len(unique_episodes(events * 3)) == 1
    assert events[0]["attention_seconds"] is None
    assert events[0]["attention_provenance"] == "unmeasured_scripted_action"
    with pytest.raises(ValueError, match="Conflicting"):
        unique_episodes(events + [{**events[0], "attention_seconds": 10}])


def test_brief_arithmetic_without_borrowed_human_savings():
    result = project({"example": 1}, {"example": 1})
    assert result["incremental_cost"] == 5200
    assert result["break_even_seconds"] == 39
    assert result["cash_break_even_positive_seconds"] == 78
    assert result["capacity_hours"] == 200
    assert result["net_capacity_value"] == 2800
    assert result["conditional_cash_impact"] == -1200


def test_zero_realization_and_negative_labor_are_not_discounted():
    result = project(
        {"saving": 2, "extra": -1}, {"saving": 0.5, "extra": 0.5}, realization_fraction=0
    )
    assert result["conditional_cash_impact"] == -4000 - 5200
    assert result["cash_break_even_positive_seconds"] is None
    assert result["cash_at_50_percent"] == 0.5 * 8000 - 4000 - 5200


def test_volume_cannot_rescue_negative_unit_economics():
    result = project({"no_saving": 0}, {"no_saving": 1})
    assert result["volume_break_even_orders_per_month"] is None
    assert result["months_to_capacity_break_even"] is None
    assert result["months_to_cash_break_even"] is None


@pytest.mark.parametrize("weights", [{"x": -1}, {"x": 0}, {"x": float("nan")}])
def test_bad_weighting_is_not_silently_accepted(weights):
    with pytest.raises(ValueError):
        normalized(weights)


def test_explicit_weight_normalization():
    assert normalized({"a": 1, "b": 3}) == {"a": 0.25, "b": 0.75}


def test_financial_transaction_value_is_not_an_economic_input():
    with pytest.raises(TypeError):
        project({"x": 0}, {"x": 1}, held_funds=1000000)
