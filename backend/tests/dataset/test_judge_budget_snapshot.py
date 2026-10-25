import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.judge_journey import budget_snapshot


def test_live_budget_reporting_reads_same_ledger_without_refill_or_credentials(tmp_path):
    ledger = tmp_path / "budget.sqlite3"
    with sqlite3.connect(ledger) as db:
        db.execute(
            "CREATE TABLE calls(status TEXT, actual_micro_usd INTEGER, reserved_micro_usd INTEGER)"
        )
        db.execute("INSERT INTO calls VALUES('COMPLETE',125000,200000)")
        db.execute("CREATE TABLE allocation(id INTEGER, final_reserve_micro INTEGER)")
        db.execute("INSERT INTO allocation VALUES(1,1000000)")
    access = tmp_path / "access.json"
    access.write_text(
        json.dumps(
            {
                "authorization": {"ledger": str(ledger), "model": "test"},
                "maximum_usd": 2,
                "credential_file": "must-not-be-read",
            }
        ),
        encoding="utf-8",
    )
    config = {
        "model_access": str(access),
        "model_access_sha256": hashlib.sha256(access.read_bytes()).hexdigest(),
    }
    before = ledger.read_bytes()
    snapshot = budget_snapshot(config)
    assert snapshot["requests"] == 1 and snapshot["active"] == 0
    assert snapshot["remaining_usd"] == 0.875
    assert ledger.read_bytes() == before
    config["model_access_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="changed"):
        budget_snapshot(config)
    assert budget_snapshot({}) is None
