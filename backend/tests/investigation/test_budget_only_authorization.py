"""Explicit budget-only continuation: no provider calls or real ledgers."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.bounded_client import remaining_timeout
from app.agents.budget import BudgetExceeded, ModelBudget
from tests.investigation.test_model_cutoff_races import Transport, invoke


def previous(tmp_path):
    now = datetime.now(UTC)
    ledger = ModelBudget(
        tmp_path / "budget.db",
        maximum_usd=5,
        cutoff=(now - timedelta(hours=3)).isoformat(),
        final_reserve_usd=1,
    )
    ledger.register_authorized_window(
        "old",
        starts_at=(now - timedelta(hours=2)).isoformat(),
        cutoff=(now - timedelta(hours=1)).isoformat(),
        authorization_sha256="a" * 64,
    )
    return ledger


def register(ledger, **overrides):
    ledger.register_budget_authorization(
        "budget-only",
        **{
            "replaces_window_id": "old",
            "maximum_usd": 3,
            "authorization_sha256": "b" * 64,
            **overrides,
        },
    )


def current(ledger, **overrides):
    return ModelBudget(
        ledger.path,
        **{"maximum_usd": 45, "cutoff": None, "window_id": "budget-only", **overrides},
    )


def test_explicit_budget_only_keeps_history_spend_reserve_and_persisted_cap(tmp_path):
    ledger = previous(tmp_path)
    with ledger.connect() as db:
        before = db.execute("SELECT * FROM authorized_windows").fetchall()
        policy = db.execute("SELECT * FROM budget_policy").fetchall()
        db.execute(
            "INSERT INTO calls(id,status,reserved_micro_usd) "
            "VALUES('uncertain','FAILED_UNKNOWN_USAGE',1950000)"
        )
    register(ledger)
    resumed = current(ledger)
    assert resumed.cutoff is None
    assert resumed.maximum == 3_000_000  # An env/config value of $45 cannot refill it.
    assert resumed.summary()["conservative_committed_usd"] == 1.95
    assert resumed.summary()["final_evaluation_reserve_usd"] == 1
    call = resumed.reserve("small", "claude-opus-5-5", {}, 1)
    resumed.finish(call, failed=True)
    with pytest.raises(BudgetExceeded, match="dollar cap"):
        current(ledger).reserve("over dollars after restart", "claude-opus-5-5", {}, 1)
    with resumed.connect() as db:
        assert db.execute("SELECT * FROM authorized_windows").fetchall() == before
        assert db.execute("SELECT * FROM budget_policy").fetchall() == policy
        assert db.execute("SELECT window_id FROM calls WHERE id=?", (call,)).fetchone() == (
            "budget-only",
        )
    with pytest.raises(BudgetExceeded, match="closed"):
        ModelBudget(ledger.path, cutoff=ledger.cutoff.isoformat()).check_window()


def test_missing_cutoff_is_not_implicit_authorization(tmp_path, monkeypatch):
    ledger = previous(tmp_path)
    for identifier in (None, "unknown", "old"):
        with pytest.raises(BudgetExceeded, match="registered"):
            current(ledger, window_id=identifier)
    with pytest.raises(BudgetExceeded):
        ModelBudget(tmp_path / "absent.db", cutoff=None, window_id="budget-only")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("APPLICATION_MODEL_BUDGET_PATH", str(ledger.path))
    monkeypatch.setenv("APPLICATION_MODEL_BUDGET_USD", "45")
    monkeypatch.setenv("APPLICATION_MODEL_CONCURRENCY", "1")
    monkeypatch.setenv("APPLICATION_MODEL_WINDOW_ID", "budget-only")
    monkeypatch.delenv("APPLICATION_MODEL_CUTOFF_AT", raising=False)
    with pytest.raises(BudgetExceeded, match="registered"):
        ModelBudget.configured()
    register(ledger)
    assert ModelBudget.configured().summary()["cutoff"] is None
    monkeypatch.setenv("ENABLE_PAID_MODELS", "false")
    with pytest.raises(BudgetExceeded, match="disabled"):
        ModelBudget.configured()


def test_registration_is_immutable_and_rejects_active_or_unknown_predecessor(tmp_path):
    ledger = previous(tmp_path)
    with pytest.raises(BudgetExceeded, match="replace"):
        register(ledger, replaces_window_id="missing")
    with ledger.connect() as db:
        db.execute(
            "INSERT INTO calls(id,status,reserved_micro_usd) VALUES('pending','RESERVED',100)"
        )
    with pytest.raises(BudgetExceeded, match="outstanding"):
        register(ledger)
    ledger.finish("pending", failed=True)
    register(ledger)
    register(ledger)  # Exact retry, not new money.
    with pytest.raises(BudgetExceeded, match="immutable"):
        register(ledger, maximum_usd=4)
    with pytest.raises(BudgetExceeded, match="Invalid"):
        register(ledger, maximum_usd=6)


@pytest.mark.parametrize("kind", ["parse", "raw", "async"])
def test_budget_only_sdk_paths_keep_request_timeout_and_accounting(tmp_path, kind):
    ledger = previous(tmp_path)
    register(ledger)
    resumed = current(ledger)
    assert remaining_timeout(resumed) == 60
    transport = Transport(raw=kind == "raw")
    invoke(kind, resumed, transport)
    assert len(transport.calls) == 1
    assert transport.calls[0]["timeout"] == 60
    assert resumed.summary()["known_cost_usd"] == 0.000024


def test_budget_only_still_enforces_concurrency_and_unknown_usage(tmp_path):
    ledger = previous(tmp_path)
    register(ledger)
    resumed = current(ledger, concurrency=1)
    call = resumed.reserve("first", "claude-opus-5-5", {}, 1)
    with pytest.raises(BudgetExceeded, match="concurrency"):
        current(ledger, concurrency=1).reserve("parallel", "claude-opus-5-5", {}, 1)
    resumed.finish(call, failed=True)
    assert current(ledger).summary()["conservative_committed_usd"] > 0


def test_harness_registers_exact_cap_without_refill_and_clears_expired_env(tmp_path, monkeypatch):
    import connected_model_qualification as harness

    ledger = previous(tmp_path)
    auth = {
        "authorization_mode": "budget_only",
        "authorization_id": "budget-only",
        "replaces_window_id": "old",
        "maximum_cumulative_usd": 3,
        "cutoff": None,
        "ledger": str(ledger.path),
        "model": "claude-opus-5-5",
        "payments": "mock",
        "production_activation": False,
        "concurrency": 1,
    }
    auth_path, access_path = tmp_path / "authorization.json", tmp_path / "access.json"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    monkeypatch.setattr(harness, "AUTH", auth_path)
    monkeypatch.setattr(harness, "ACCESS", access_path)
    access = harness.authorize()
    assert access["maximum_usd"] == 3
    assert harness.authorize() == access
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("APPLICATION_MODEL_CUTOFF_AT", ledger.cutoff.isoformat())
    # configure mutates env deliberately; isolate every changed field in this test.
    for name in (
        "CLAUDE_MODEL",
        "ENABLE_PAID_MODELS",
        "ENABLE_DATASET_MODEL_ASSESSMENT",
        "PAYMENT_ADAPTER",
        "ENABLE_TESTNET_BROADCAST",
        "ENABLE_BROKER_DISPUTE_ASSESSMENT",
        "APPLICATION_MODEL_BUDGET_PATH",
        "APPLICATION_MODEL_WINDOW_ID",
        "APPLICATION_MODEL_BUDGET_USD",
        "APPLICATION_MODEL_CONCURRENCY",
    ):
        monkeypatch.setenv(name, "test-placeholder")
    configured = harness.configure()
    assert configured.cutoff is None and configured.maximum == 3_000_000
    assert configured.summary()["requests_used"] == 0
    assert harness.authorize() == access
    auth["maximum_cumulative_usd"] = 4
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not match"):
        harness.authorize()
