import hashlib

import pytest
from fastapi.testclient import TestClient

from app.contracts.catalog import AcceptQuoteCommand, CatalogOrder
from app.main import create_app
from app.orders.service import DomainError
from tests.catalog.fixtures import accepted, cmd, draft_quote, repaired


def client_for(service, clock):
    return TestClient(
        create_app(
            service.repository.path, artifact_root=service.store.root, clock=clock, run_worker=False
        )
    )


def test_committed_stream_exact_bindings_and_restart(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    run_id = order.snapshot.order_id
    with client_for(service, clock) as client:
        first = client.get(f"/api/runs/{run_id}/events").json()
        events = first["events"]
        assert len(events) >= 5
        assert [e["seq"] for e in events] == sorted({e["seq"] for e in events})
        assert len({e["event_id"] for e in events}) == len(events)
        last = events[-1]
        assert last["order"] == order.model_dump(mode="json")
        assert last["binding"] == order.binding.model_dump()
        assert last["aggregate_revision"] == order.revision
        assert (
            last["accepted_snapshot_sha256"]
            == hashlib.sha256(order.snapshot.model_dump_json().encode()).hexdigest()
        )
        assert last["payment"]["payment"]["state"] == "funded"
        assert last["payment"]["simulated"] is True
        assert last["payment"]["explorer_links"] == []
        assert (
            client.get(f"/api/runs/{run_id}/events?after={first['next_cursor']}").json()["events"]
            == []
        )
        assert client.get("/api/runs/").json()[0]["run_id"] == run_id
    with client_for(service, clock) as client:
        assert client.get(f"/api/runs/{run_id}/events").json()["events"] == events


def test_poll_and_replay_do_not_advance_expired_review_or_capture(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    run_id = order.snapshot.order_id
    with client_for(service, clock) as client:
        before = client.get(f"/api/runs/{run_id}/events").json()["events"]
        clock.advance(60)
        for _ in range(3):
            assert client.get(f"/api/runs/{run_id}/events").json()["events"] == before
        with service.repository.transaction() as db:
            raw = service.repository.load(db, "order", run_id, CatalogOrder)
        assert raw.order_state == "delivered" and not raw.ledger
        service.expire_due()
        after = client.get(f"/api/runs/{run_id}/events?after={before[-1]['seq']}").json()
        assert len(after["events"]) == 1
        assert after["events"][0]["payment"]["payment"]["state"] == "captured"


def test_idempotency_and_stale_commands_cannot_duplicate_events(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    run_id = order.snapshot.order_id
    command = cmd(order, "accept-delivery")
    service.mutate(run_id, "accept", command)
    with client_for(service, clock) as client:
        before = client.get(f"/api/runs/{run_id}/events").json()["events"]
        service.mutate(run_id, "accept", command)
        with pytest.raises(DomainError):
            service.mutate(run_id, "accept", cmd(order, "stale-command"))
        assert client.get(f"/api/runs/{run_id}/events").json()["events"] == before
        assert len(before[-1]["order"]["ledger"]) == 1


def test_event_append_and_financial_state_roll_back_together(setup, monkeypatch):
    service, _, _ = setup
    _, quote = draft_quote(service)

    def broken(*args, **kwargs):
        raise RuntimeError("injected event write failure")

    monkeypatch.setattr("app.orders.catalog.append_catalog_event", broken)
    with pytest.raises(RuntimeError, match="injected event"):
        service.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id, customer_actor="customer:test", idempotency_key="accept"
            )
        )
    with service.repository.transaction() as db:
        assert (
            db.execute("SELECT count(*) FROM catalog_records WHERE kind='order'").fetchone()[0] == 0
        )
        assert db.execute("SELECT count(*) FROM catalog_run_events").fetchone()[0] == 0


def test_run_endpoint_does_not_create_runs_or_accept_desired_verdict(setup):
    service, clock, _ = setup
    with client_for(service, clock) as client:
        assert client.post("/api/runs/", json={"ending": "maya"}).status_code == 405
        assert client.get("/api/runs/missing/events").status_code == 404
        assert client.get("/api/runs/").json() == []
        order = accepted(service)
        assert client.get(f"/api/runs/{order.snapshot.order_id}/events?after=-1").status_code == 422
