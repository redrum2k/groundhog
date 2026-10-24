"""Shared, fail-closed request/cost/concurrency reservations for authorized app calls."""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4


class BudgetExceeded(RuntimeError):
    pass


class ModelBudget:
    # Standard global Opus 5.5 list price, verified 2026-10-24. No fast mode/tools.
    INPUT_MICRO_USD = 4
    OUTPUT_MICRO_USD = 20

    def __init__(self, path, *, maximum_usd=45, concurrency=2, cutoff, final_reserve_usd=0):
        self.path = Path(path)
        self.maximum = int(Decimal(str(maximum_usd)) * 1_000_000)
        self.concurrency = min(2, int(concurrency))
        self.cutoff = datetime.fromisoformat(cutoff)
        if not 0 < self.maximum <= 45_000_000 or self.concurrency < 1:
            raise BudgetExceeded("Invalid approved resource envelope")
        if self.cutoff.tzinfo is None:
            raise BudgetExceeded("Budget requires an absolute cutoff")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, purpose TEXT, "
                "model TEXT, request_sha256 TEXT, started_at TEXT, finished_at TEXT, "
                "status TEXT, reserved_micro_usd INTEGER, actual_micro_usd INTEGER, "
                "input_tokens INTEGER, output_tokens INTEGER, usage_json TEXT)"
            )
            columns = {r[1] for r in db.execute("PRAGMA table_info(calls)")}
            if "failure_signature" not in columns:
                db.execute("ALTER TABLE calls ADD COLUMN failure_signature TEXT")
            db.execute(
                "CREATE TABLE IF NOT EXISTS allocation (id INTEGER PRIMARY KEY CHECK(id=1), "
                "final_reserve_micro INTEGER NOT NULL, plan_sha256 TEXT, reason TEXT)"
            )
            db.execute(
                "INSERT OR IGNORE INTO allocation VALUES(1,?,NULL,?)",
                (
                    int(Decimal(str(final_reserve_usd)) * 1_000_000),
                    "Initial prereveal holdback; revise after measured development pilot",
                ),
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS model_cooldown "
                "(id INTEGER PRIMARY KEY CHECK(id=1), until_at TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS budget_policy "
                "(id INTEGER PRIMARY KEY CHECK(id=1), maximum_micro INTEGER, cutoff TEXT)"
            )
            db.execute(
                "INSERT OR IGNORE INTO budget_policy VALUES(1,?,?)",
                (self.maximum, self.cutoff.isoformat()),
            )
            maximum, cutoff = db.execute(
                "SELECT maximum_micro,cutoff FROM budget_policy WHERE id=1"
            ).fetchone()
            # A resumed process cannot reset spent dollars or extend the original clock.
            self.maximum = min(self.maximum, maximum)
            self.cutoff = min(self.cutoff, datetime.fromisoformat(cutoff))

    @classmethod
    def configured(cls):
        if os.getenv("ENABLE_PAID_MODELS") != "true":
            raise BudgetExceeded("Application API calls are disabled")
        if os.getenv("CLAUDE_MODEL") != "claude-opus-5-5":
            raise BudgetExceeded(
                "This approved price envelope requires CLAUDE_MODEL=claude-opus-5-5"
            )
        path = os.getenv("APPLICATION_MODEL_BUDGET_PATH")
        cutoff = os.getenv("APPLICATION_MODEL_CUTOFF_AT")
        if not path or not cutoff:
            raise BudgetExceeded("Durable model budget/cutoff is not configured")
        return cls(
            path,
            maximum_usd=os.getenv("APPLICATION_MODEL_BUDGET_USD", "0"),
            concurrency=os.getenv("APPLICATION_MODEL_CONCURRENCY", "0"),
            cutoff=cutoff,
            final_reserve_usd=os.getenv("APPLICATION_MODEL_FINAL_RESERVE_USD", "20"),
        )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, purpose, model, payload, max_tokens, *, final_evaluation=False):
        if model != "claude-opus-5-5":
            raise BudgetExceeded("Model is outside the priced envelope")
        if datetime.now(UTC) >= self.cutoff:
            raise BudgetExceeded("Absolute V6 model-call cutoff reached")
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 16384
        ):
            raise BudgetExceeded("Each request requires a positive bounded output-token limit")
        encoded = json.dumps(payload, sort_keys=True).encode()
        request_hash = hashlib.sha256(encoded).hexdigest()
        # Deliberately conservative UTF-8 bound plus protocol/schema allowance.
        # No caching, built-in tools, fast mode, batches or region surcharge requested.
        reserved = (2 * len(encoded) + 8192) * 4 + int(max_tokens) * 20
        identifier = f"call-{uuid4().hex}"
        with self.connect() as db:
            _, active, committed = db.execute(
                "SELECT count(*),coalesce(sum(status='RESERVED'),0),"
                "coalesce(sum(coalesce(actual_micro_usd,reserved_micro_usd)),0) FROM calls"
            ).fetchone()
            reserve, plan = db.execute(
                "SELECT final_reserve_micro,plan_sha256 FROM allocation WHERE id=1"
            ).fetchone()
            if final_evaluation and not plan:
                raise BudgetExceeded("Final evaluation requires a frozen plan digest")
            limit = self.maximum if final_evaluation else self.maximum - reserve
            if active >= self.concurrency or committed + reserved > limit:
                raise BudgetExceeded(
                    "Application concurrency/dollar cap or final-evaluation reserve reached"
                )
            previous = db.execute(
                "SELECT status,failure_signature FROM calls WHERE purpose=? "
                "AND request_sha256=? ORDER BY rowid DESC LIMIT 3",
                (purpose, request_hash),
            ).fetchall()
            if len(previous) >= 3:
                raise BudgetExceeded(
                    "Repeated identical request without new information; stop this loop"
                )
            recent = db.execute(
                "SELECT failure_signature FROM calls WHERE purpose=? AND model=? "
                "ORDER BY rowid DESC LIMIT 3",
                (purpose, model),
            ).fetchall()
            if len(recent) == 3 and recent[0][0] and all(r[0] == recent[0][0] for r in recent):
                raise BudgetExceeded(
                    "Repeated identical provider failures; diagnose this lane before continuing"
                )
            cooldown = db.execute("SELECT until_at FROM model_cooldown WHERE id=1").fetchone()
            if cooldown and datetime.now(UTC) < datetime.fromisoformat(cooldown[0]):
                raise BudgetExceeded("Provider rate-limit cooldown is active")
            db.execute(
                "INSERT INTO calls(id,purpose,model,request_sha256,started_at,status,"
                "reserved_micro_usd) "
                "VALUES(?,?,?,?,?,'RESERVED',?)",
                (
                    identifier,
                    purpose,
                    model,
                    request_hash,
                    datetime.now(UTC).isoformat(),
                    reserved,
                ),
            )
        return identifier

    def finish(
        self, identifier, usage=None, *, failed=False, failure_signature=None, cooldown_seconds=0
    ):
        data = usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage
        actual = None
        if data is not None:
            creation = data.get("cache_creation") or {}
            cache_cost = (
                int(creation.get("ephemeral_5m_input_tokens") or 0) * 5
                + int(creation.get("ephemeral_1h_input_tokens") or 0) * 8
            )
            if not creation:
                cache_cost = int(data.get("cache_creation_input_tokens") or 0) * 8
            # Thinking is part of output_tokens, not an extra charge. Preserve its
            # breakdown and cache metadata in usage_json without double counting.
            actual = (
                int(data.get("input_tokens", 0)) * 4
                + int(data.get("output_tokens", 0)) * 20
                + cache_cost
                + (int(data.get("cache_read_input_tokens") or 0) + 4) // 5
            )
        with self.connect() as db:
            db.execute(
                "UPDATE calls SET finished_at=?,status=?,actual_micro_usd=?,"
                "input_tokens=?,output_tokens=?,usage_json=?,failure_signature=? "
                "WHERE id=? AND status='RESERVED'",
                (
                    datetime.now(UTC).isoformat(),
                    "FAILED_UNKNOWN_USAGE" if failed else "COMPLETE",
                    actual,
                    data.get("input_tokens") if data else None,
                    data.get("output_tokens") if data else None,
                    json.dumps(data) if data else None,
                    failure_signature,
                    identifier,
                ),
            )
            if cooldown_seconds:
                from datetime import timedelta

                until = (datetime.now(UTC) + timedelta(seconds=cooldown_seconds)).isoformat()
                db.execute(
                    "INSERT INTO model_cooldown VALUES(1,?) ON CONFLICT(id) "
                    "DO UPDATE SET until_at=max(until_at,excluded.until_at)",
                    (until,),
                )

    def allocate_final(self, reserve_usd, *, plan_sha256=None, reason):
        amount = int(Decimal(str(reserve_usd)) * 1_000_000)
        if not 0 <= amount <= self.maximum or not reason:
            raise BudgetExceeded("Invalid final evaluation allocation")
        if plan_sha256 and (
            len(plan_sha256) != 64 or any(c not in "0123456789abcdef" for c in plan_sha256)
        ):
            raise BudgetExceeded("Frozen plan digest must be SHA-256")
        with self.connect() as db:
            db.execute(
                "UPDATE allocation SET final_reserve_micro=?,plan_sha256=?,reason=? WHERE id=1",
                (amount, plan_sha256, reason),
            )

    def summary(self):
        with self.connect() as db:
            final_reserve, plan = db.execute(
                "SELECT final_reserve_micro,plan_sha256 FROM allocation WHERE id=1"
            ).fetchone()
            count, active, actual, conservative = db.execute(
                "SELECT count(*),coalesce(sum(status='RESERVED'),0),"
                "coalesce(sum(actual_micro_usd),0),"
                "coalesce(sum(coalesce(actual_micro_usd,reserved_micro_usd)),0) FROM calls"
            ).fetchone()
        return {
            "requests_used": count,
            "request_count_ceiling": None,
            "final_evaluation_reserve_usd": final_reserve / 1_000_000,
            "frozen_evaluation_plan_sha256": plan,
            "active": active,
            "known_cost_usd": actual / 1_000_000,
            "conservative_committed_usd": conservative / 1_000_000,
            "maximum_usd": self.maximum / 1_000_000,
            "cutoff": self.cutoff.isoformat(),
        }
