from datetime import UTC, datetime, timedelta

import pytest

from app.agents.budget import BudgetExceeded, ModelBudget


def test_new_authorization_preserves_old_cutoff_and_cumulative_spend(tmp_path):
    now = datetime.now(UTC)
    old_cutoff = (now - timedelta(hours=1)).isoformat()
    ledger = ModelBudget(tmp_path / "budget.sqlite3", cutoff=old_cutoff)
    with ledger.connect() as db:
        db.execute(
            "INSERT INTO calls(id,status,reserved_micro_usd) "
            "VALUES('old','FAILED_UNKNOWN_USAGE',44000000)"
        )
    end = (now + timedelta(hours=1)).isoformat()
    with pytest.raises(BudgetExceeded):
        ModelBudget(ledger.path, cutoff=end, window_id="followup")
    ledger.register_authorized_window(
        "followup", starts_at=now.isoformat(), cutoff=end, authorization_sha256="a" * 64
    )
    current = ModelBudget(ledger.path, cutoff=end, window_id="followup")
    assert current.summary()["conservative_committed_usd"] == 44
    assert current.cutoff.isoformat() == end
    call = current.reserve("small", "claude-opus-5-5", {}, 10)
    current.finish(call, {"input_tokens": 1, "output_tokens": 1})
    with pytest.raises(BudgetExceeded):
        current.reserve("too-large", "claude-opus-5-5", {"text": "x" * 200000}, 16384)
    assert ModelBudget(ledger.path, cutoff=end).cutoff.isoformat() == old_cutoff
    with pytest.raises(BudgetExceeded):
        ledger.register_authorized_window(
            "followup",
            starts_at=now.isoformat(),
            cutoff=(now + timedelta(hours=2)).isoformat(),
            authorization_sha256="a" * 64,
        )
    with ledger.connect() as db:
        assert db.execute("SELECT cutoff FROM budget_policy").fetchone()[0] == old_cutoff
        assert (
            db.execute("SELECT window_id FROM calls WHERE id=?", (call,)).fetchone()[0]
            == "followup"
        )


def test_new_window_rejects_overlap_excess_duration_and_active_calls(tmp_path):
    now = datetime.now(UTC)
    ledger = ModelBudget(tmp_path / "budget.sqlite3", cutoff=(now - timedelta(hours=1)).isoformat())
    with pytest.raises(BudgetExceeded):
        ledger.register_authorized_window(
            "bad",
            starts_at=now.isoformat(),
            cutoff=(now + timedelta(hours=3)).isoformat(),
            authorization_sha256="b" * 64,
        )
    with ledger.connect() as db:
        db.execute(
            "INSERT INTO calls(id,status,reserved_micro_usd) VALUES('inflight','RESERVED',100000)"
        )
    with pytest.raises(BudgetExceeded):
        ledger.register_authorized_window(
            "new",
            starts_at=now.isoformat(),
            cutoff=(now + timedelta(hours=1)).isoformat(),
            authorization_sha256="b" * 64,
        )
