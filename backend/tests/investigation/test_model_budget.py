from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.agents.bounded_client import BoundedClient, selected_model
from app.agents.budget import BudgetExceeded, ModelBudget


def budget(tmp_path, **kwargs):
    return ModelBudget(
        tmp_path / "budget.sqlite3",
        cutoff=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        **kwargs,
    )


def test_durable_concurrency_limits_include_uncertain_calls_without_count_ceiling(tmp_path):
    ledger = budget(tmp_path)
    first = ledger.reserve("test", "claude-opus-5-5", {}, 10)
    second = ledger.reserve("test", "claude-opus-5-5", {}, 10)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("third concurrent", "claude-opus-5-5", {}, 10)
    ledger.finish(first, failed=True)
    assert ledger.summary()["conservative_committed_usd"] > 0
    ledger.finish(second, {"input_tokens": 100, "output_tokens": 20})
    restarted = budget(tmp_path)
    third = restarted.reserve("last", "claude-opus-5-5", {}, 10)
    restarted.finish(third, {"input_tokens": 1, "output_tokens": 1})
    fourth = restarted.reserve("new informative work", "claude-opus-5-5", {"new_evidence": 4}, 10)
    restarted.finish(fourth, {"input_tokens": 1, "output_tokens": 1})
    assert restarted.summary()["requests_used"] == 4
    assert restarted.summary()["request_count_ceiling"] is None


def test_more_than_500_small_distinct_calls_are_allowed_by_dollars(tmp_path):
    ledger = budget(tmp_path)
    for index in range(501):
        call = ledger.reserve("distinct-world", "claude-opus-5-5", {"world": index}, 1)
        ledger.finish(call, {"input_tokens": 1, "output_tokens": 1})
    assert ledger.summary()["requests_used"] == 501
    assert ledger.summary()["known_cost_usd"] == 0.012024


def test_nonproductive_loop_stops_without_blocking_independent_work(tmp_path):
    ledger = budget(tmp_path)
    for _ in range(3):
        call = ledger.reserve("same-loop", "claude-opus-5-5", {"unchanged": True}, 1)
        ledger.finish(call, failed=True, failure_signature="TimeoutError")
    with pytest.raises(BudgetExceeded, match="identical"):
        ledger.reserve("same-loop", "claude-opus-5-5", {"unchanged": True}, 1)
    ledger.reserve("other-objective", "claude-opus-5-5", {"new_information": True}, 1)


def test_final_reserve_and_cache_thinking_accounting(tmp_path):
    ledger = budget(tmp_path, maximum_usd=1, final_reserve_usd=0.99)
    with pytest.raises(BudgetExceeded, match="reserve"):
        ledger.reserve("development", "claude-opus-5-5", {}, 1)
    with pytest.raises(BudgetExceeded, match="frozen"):
        ledger.reserve("final", "claude-opus-5-5", {}, 1, final_evaluation=True)
    ledger.allocate_final(0.99, plan_sha256="a" * 64, reason="Measured frozen pilot forecast")
    call = ledger.reserve("final", "claude-opus-5-5", {}, 100, final_evaluation=True)
    ledger.finish(
        call,
        {
            "input_tokens": 10,
            "output_tokens": 100,
            "output_tokens_details": {"thinking_tokens": 80},
            "cache_creation_input_tokens": 30,
            "cache_creation": {"ephemeral_5m_input_tokens": 20, "ephemeral_1h_input_tokens": 10},
            "cache_read_input_tokens": 100,
        },
    )
    assert ledger.summary()["known_cost_usd"] == 0.002240


def test_dollar_deadline_and_model_caps_are_preflight(tmp_path):
    ledger = budget(tmp_path, maximum_usd=0.01)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("over dollars", "claude-opus-5-5", {}, 100)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("different model", "other", {}, 1)
    ledger.cutoff = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(BudgetExceeded, match="cutoff"):
        ledger.reserve("late", "claude-opus-5-5", {}, 1)
    assert ledger.summary()["requests_used"] == 0


def test_sdk_failure_is_not_free_or_automatically_retried(tmp_path):
    calls = []

    class Transport:
        def parse(self, **kwargs):
            calls.append(kwargs)
            raise TimeoutError("test timeout")

    ledger = budget(tmp_path)
    client = BoundedClient(client=SimpleNamespace(messages=Transport()), budget=ledger)
    with pytest.raises(TimeoutError):
        client.parse(model="claude-opus-5-5", max_tokens=10, messages=[])
    assert len(calls) == 1
    assert ledger.summary()["requests_used"] == 1
    assert ledger.summary()["active"] == 0
    assert ledger.summary()["conservative_committed_usd"] > 0


def test_claude_model_is_authoritative(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("ANTHROPIC_MODEL", "legacy-model")
    monkeypatch.setenv("OBJECTION_MODEL", "never-use-this")
    assert selected_model() == "claude-opus-5-5"


def test_restart_cannot_extend_original_deadline_or_envelope(tmp_path):
    original = budget(tmp_path, maximum_usd=1)
    resumed = ModelBudget(
        tmp_path / "budget.sqlite3",
        maximum_usd=45,
        cutoff=(datetime.now(UTC) + timedelta(hours=8)).isoformat(),
    )
    assert resumed.maximum == original.maximum
    assert resumed.cutoff == original.cutoff
