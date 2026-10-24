"""The retained invoice workflow must not alter the catalog API or historical data."""

import asyncio
from threading import Event

from fastapi.testclient import TestClient

from app.contracts.catalog import CatalogOrder
from app.contracts.jobflow import OrderCreate
from app.main import create_app
from tests.catalog.fixtures import accepted, repaired


def test_both_api_surfaces_keep_their_own_contracts_and_orders(setup, monkeypatch):
    service, clock, _ = setup
    catalog = accepted(service)
    monkeypatch.setenv("JOBFLOW_DEMO", "1")
    app = create_app(
        service.repository.path, artifact_root=service.store.root, clock=clock, run_worker=False
    )
    with TestClient(app) as client:
        invoice = app.state.jobflow.create(
            app.state.jobflow.actors()[0],
            OrderCreate(
                idempotency_key="invoice",
                document_count=1,
                failed_count=0,
                disputed_field=None,
                requested_fields=[],
            ),
        )
        root_schema = client.get("/openapi.json").json()
        invoice_schema = client.get("/api/jobflow/openapi.json").json()
        assert "FundingAuthorization" in root_schema["components"]["schemas"]
        assert "/quote-acceptance" in root_schema["paths"]
        assert "/orders/{order_id}/commands" in invoice_schema["paths"]
        assert "/orders/{order_id}/commands" not in root_schema["paths"]
        assert client.get(f"/orders/{catalog.snapshot.order_id}").json()["payment"]
        assert client.get(f"/orders/{invoice.id}").status_code == 404
        token = client.post("/api/jobflow/sessions", json={"actor_id": "customer"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get(f"/api/jobflow/orders/{invoice.id}", headers=headers).status_code == 200
        assert (
            client.get(
                f"/api/jobflow/orders/{catalog.snapshot.order_id}", headers=headers
            ).status_code
            == 404
        )


def test_invoice_deadline_sweep_leaves_unrelated_historical_bytes_untouched(setup):
    service, clock, _ = setup
    raw = '{"policy":"unrelated historical invoice"}'
    with service.repository.transaction() as db:
        db.execute("INSERT INTO orders VALUES (?,?)", ("historical", raw))
    app = create_app(service.repository.path, clock=clock, run_worker=False)
    with TestClient(app):
        clock.advance(4000)
        assert app.state.jobflow.base.expire_due() == 0
        with service.repository.transaction() as db:
            assert (
                db.execute("SELECT data FROM orders WHERE order_id='historical'").fetchone()[0]
                == raw
            )


def test_invoice_execution_does_not_block_catalog_deadlines(setup, monkeypatch):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    entered, release, swept = Event(), Event(), Event()

    async def slow_invoice_work(_service):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        return False

    monkeypatch.setattr("app.main.run_once", slow_invoice_work)
    app = create_app(
        service.repository.path, artifact_root=service.store.root, clock=clock, run_worker=True
    )
    with TestClient(app):
        try:
            assert entered.wait(2)
            original = app.state.orders.expire_due

            def sweep():
                changed = original()
                if clock() >= order.deliveries[-1].review_deadline:
                    swept.set()
                return changed

            app.state.orders.expire_due = sweep
            clock.advance(60)
            assert swept.wait(3)
            with service.repository.transaction() as db:
                current = service.repository.load(
                    db, "order", order.snapshot.order_id, CatalogOrder
                )
            assert current.order_state == "closed" and len(current.ledger) == 1
        finally:
            release.set()
