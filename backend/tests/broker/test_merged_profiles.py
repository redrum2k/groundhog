"""Profile integration must not change the catalog default or mix payment clocks."""

from fastapi.testclient import TestClient

from app.contracts.jobflow import OrderCreate
from app.main import create_app
from app.runtime.broker import Broker
from app.runtime.jobflow import Jobflow
from tests.broker.conftest import ACTORS, accept_order, command
from tests.catalog.fixtures import repaired


def test_catalog_invoice_and_broker_keep_separate_contracts_in_one_app(setup):
    service, clock, fixtures = setup
    catalog = repaired(service, fixtures)
    jobflow = Jobflow(service.repository.path, demo=True, clock=clock)
    broker = Broker(jobflow)
    regional = command(broker, accept_order(broker), "provider", "produce")
    invoice = jobflow.create(
        ACTORS["customer"],
        OrderCreate(
            idempotency_key="profile-invoice",
            document_count=1,
            failed_count=0,
            disputed_field=None,
            requested_fields=[],
        ),
    )
    app = create_app(service=jobflow, artifact_root=service.store.root, run_worker=False)
    with TestClient(app) as client:
        root = client.get("/openapi.json").json()
        assert root["info"]["title"] == "Catalog order to cash"
        assert "FundingAuthorization" in root["components"]["schemas"]
        assert "BrokerRecord" not in root["components"]["schemas"]
        assert "/quote-acceptance" in root["paths"]
        assert "/drafts" in client.get("/api/broker/openapi.json").json()["paths"]
        assert "/commands" in client.get("/api/improvements/openapi.json").json()["paths"]
        token = client.post("/api/jobflow/sessions", json={"actor_id": "customer"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get(f"/orders/{catalog.snapshot.order_id}").status_code == 200
        assert client.get(f"/api/jobflow/orders/{invoice.id}", headers=headers).status_code == 200
        assert client.get(f"/api/broker/orders/{regional.id}", headers=headers).status_code == 200
        assert client.get(f"/orders/{regional.id}").status_code == 404
        assert client.get(f"/api/jobflow/orders/{regional.id}", headers=headers).status_code == 404
        assert client.get(f"/api/broker/orders/{invoice.id}", headers=headers).status_code == 404
        assert app.state.broker.store.path == app.state.orders.repository.path
        assert catalog.snapshot.quote.policy.review_seconds == 60
        assert regional.base_order.order.snapshot.policy.review_window_seconds == 600


def test_catalog_cutoff_does_not_capture_broker_at_catalog_review_deadline(setup):
    service, clock, fixtures = setup
    catalog = repaired(service, fixtures)
    jobflow = Jobflow(service.repository.path, demo=True, clock=clock)
    broker = Broker(jobflow)
    regional = command(broker, accept_order(broker), "provider", "produce")
    app = create_app(service=jobflow, artifact_root=service.store.root, run_worker=False)
    with TestClient(app):
        clock.advance(60)
        app.state.orders.expire_due()
        app.state.jobflow.base.expire_due()
        app.state.broker.expire_due()
        assert len(app.state.orders.get(catalog.snapshot.order_id).ledger) == 1
        assert not app.state.broker.view(ACTORS["customer"], regional.id).base_order.order.ledger
        clock.advance(540)
        app.state.broker.expire_due()
        assert (
            len(app.state.broker.view(ACTORS["customer"], regional.id).base_order.order.ledger) == 1
        )
        assert len(app.state.orders.get(catalog.snapshot.order_id).ledger) == 1
        app.state.broker.expire_due()
        assert (
            len(app.state.broker.view(ACTORS["customer"], regional.id).base_order.order.ledger) == 1
        )
