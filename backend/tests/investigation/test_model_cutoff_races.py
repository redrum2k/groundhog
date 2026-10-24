"""Greptile P1: deterministic cutoff races; temporary ledgers and fake SDKs only."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.agents import bounded_client
from app.agents import budget as budget_module
from app.agents.bounded_client import BoundedAsyncClient, BoundedClient, remaining_timeout
from app.agents.budget import BudgetExceeded, ModelBudget


class Clock(datetime):
    current = datetime(2026, 10, 24, 12, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    Clock.current = datetime(2026, 10, 24, 12, tzinfo=UTC)
    monkeypatch.setattr(budget_module, "datetime", Clock)
    monkeypatch.setattr(bounded_client, "datetime", Clock, raising=False)
    return ModelBudget(
        tmp_path / "budget.sqlite3", cutoff=(Clock.current + timedelta(seconds=5)).isoformat()
    )


class Reply(BaseModel):
    okay: bool


class Transport:
    def __init__(self, raw=False):
        self.calls = []
        self.messages = self
        if raw:
            self.with_raw_response = SimpleNamespace(create=self.raw)

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(usage={"input_tokens": 1, "output_tokens": 1})

    async def create(self, **kwargs):
        return self.parse(**kwargs)

    def raw(self, **kwargs):
        self.calls.append(kwargs)
        response = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text='{"okay":true}')],
            model_dump=lambda: {},
        )
        return SimpleNamespace(
            http_response=SimpleNamespace(
                json=lambda: {"usage": {"input_tokens": 1, "output_tokens": 1}}
            ),
            parse=lambda: response,
        )


def invoke(kind, ledger, transport):
    kwargs = dict(model="claude-opus-5-5", max_tokens=10, messages=[])
    if kind == "async":
        return asyncio.run(BoundedAsyncClient(client=transport, budget=ledger).create(**kwargs))
    if kind == "raw":
        kwargs["output_format"] = Reply
    return BoundedClient(client=transport, budget=ledger).parse(**kwargs)


def test_cutoff_rechecked_after_sqlite_write_lock_wait(ledger, monkeypatch):
    transport = Transport()
    waiting = Event()
    original_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "BEGIN IMMEDIATE":
                waiting.set()
            return super().execute(sql, *args, **kwargs)

    holder = original_connect(ledger.path)
    holder.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(
        budget_module.sqlite3,
        "connect",
        lambda *a, **kw: original_connect(*a, **kw, factory=ObservedConnection),
    )

    def work():
        try:
            invoke("parse", ledger, transport)
        except BudgetExceeded:
            return "closed"
        return "dispatched"

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(work)
            try:
                assert waiting.wait(3) and holder.in_transaction
                assert not future.done()
                Clock.current = ledger.cutoff
            finally:
                holder.commit()
            outcome = future.result(timeout=3)
    finally:
        holder.close()
    assert transport.calls == []
    assert outcome == "closed"
    assert ledger.summary()["requests_used"] == 0


@pytest.mark.parametrize("kind", ["parse", "raw", "async"])
def test_expiry_between_reservation_and_dispatch_is_auditable(ledger, monkeypatch, kind):
    prior = ledger.reserve("prior", "claude-opus-5-5", {}, 10)
    ledger.finish(prior, failed=True)
    committed = ledger.summary()["conservative_committed_usd"]
    original_reserve = ledger.reserve

    def reserve(*args, **kwargs):
        identifier = original_reserve(*args, **kwargs)
        Clock.current = ledger.cutoff
        return identifier

    monkeypatch.setattr(ledger, "reserve", reserve)
    transport = Transport(raw=kind == "raw")
    with pytest.raises(BudgetExceeded, match="cutoff|window"):
        invoke(kind, ledger, transport)
    assert transport.calls == []
    summary = ledger.summary()
    assert summary["active"] == 0 and summary["requests_used"] == 2
    assert summary["conservative_committed_usd"] == committed
    with ledger.connect() as db:
        row = db.execute(
            "SELECT status,actual_micro_usd,reserved_micro_usd,finished_at FROM calls WHERE id<>?",
            (prior,),
        ).fetchone()
        assert row[0] == "ABORTED_BEFORE_DISPATCH" and row[1] == 0
        assert row[2] > 0 and row[3]
        assert (
            db.execute("SELECT status FROM calls WHERE id=?", (prior,)).fetchone()[0]
            == "FAILED_UNKNOWN_USAGE"
        )


@pytest.mark.parametrize("offset", [0, 1])
def test_expired_timeout_does_not_become_nominal_one_millisecond(ledger, offset):
    Clock.current = ledger.cutoff + timedelta(seconds=offset)
    with pytest.raises(BudgetExceeded):
        remaining_timeout(ledger)


@pytest.mark.parametrize("kind", ["parse", "raw", "async"])
def test_open_window_dispatches_once_with_bounded_timeout(ledger, kind):
    transport = Transport(raw=kind == "raw")
    invoke(kind, ledger, transport)
    assert len(transport.calls) == 1
    assert 0 < transport.calls[0]["timeout"] <= 5
    assert ledger.summary()["known_cost_usd"] == 0.000024
