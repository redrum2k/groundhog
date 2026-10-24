import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.contracts.broker import DraftCreate
from app.contracts.improvement import GreyAreaIncident, ImprovementCommand
from app.improvement.service import Improvement, deterministic_proposals
from app.main import create_app
from app.storage.jobflow import uid
from tests.broker.conftest import ACTORS, accept_order, command


def session(client, actor):
    response = client.post("/api/jobflow/sessions", json={"actor_id": actor})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_authenticated_api_exposes_new_types_events_and_real_verdict(broker, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    order = command(broker, accept_order(broker, clarity=False), "provider", "produce")
    with TestClient(create_app(service=broker.jobflow, run_worker=False)) as client:
        customer, other, controller = (
            session(client, role) for role in ("customer", "customer_other", "controller")
        )
        assert client.get(f"/api/broker/orders/{order.id}").status_code == 401
        assert client.get(f"/api/broker/orders/{order.id}", headers=other).status_code == 403
        view = client.get(f"/api/broker/orders/{order.id}", headers=customer).json()
        assert view["base_order"]["order"]["data_verification"]["verdict"] == "PASS"
        assert view["base_order"]["order"]["snapshot"]["policy"]["overall_case_seconds"] == 1800
        assert not view["base_order"]["order"]["ledger"]
        events = client.get(f"/api/broker/entities/{order.id}/events", headers=customer).json()
        assert any(event["type"] == "verification.completed" for event in events)
        assert client.get(f"/orders/{order.id}").status_code == 404
        records = client.get("/api/improvements?customer_id=northwind", headers=controller).json()
        assert records["outcomes"][0]["company_staff_touches"] == 3
        request = dict(
            idempotency_key=uid("api-propose"),
            verb="propose",
            customer_id="northwind",
            mode="DETERMINISTIC_INFRASTRUCTURE",
            incident_ids=[records["incidents"][0]["id"]],
        )
        assert (
            client.post("/api/improvements/commands", headers=customer, json=request).status_code
            == 403
        )
        response = client.post("/api/improvements/commands", headers=controller, json=request)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "COMPLETE" and body["mode"] == "DETERMINISTIC_INFRASTRUCTURE"
        assert len(body["patch_ids"]) == 2
        assert (
            client.post("/api/improvements/commands", headers=controller, json=request).json()
            == body
        )
        assert (
            client.get(f"/api/improvements/jobs/{body['job_id']}", headers=other).status_code == 403
        )
        assert (
            client.get(f"/api/improvements/jobs/{body['job_id']}", headers=controller).json()[
                "status"
            ]
            == "COMPLETE"
        )
        assert client.get(
            f"/api/improvements/entities/{body['job_id']}/events", headers=controller
        ).json()


class InjectedClient:
    def __init__(self, *, malformed=False):
        self.messages = self
        self.calls = []
        self.malformed = malformed

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][0]["content"])
        incidents = [GreyAreaIncident.model_validate(item) for item in context["incidents"]]
        bundle = deterministic_proposals(incidents, context["baseline"], [])
        raw = bundle.model_dump(mode="json")
        if self.malformed:
            raw["candidates"][0]["operations"] = [{"op": "set_price", "amount": 1}]
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name="submit_patches", input=raw)],
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=123, output_tokens=45),
        )


@pytest.mark.parametrize("malformed", [False, True])
def test_model_adapter_is_bound_budgeted_and_test_double_is_never_claimed_live(
    broker, monkeypatch, malformed
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "injected-test-sentinel-not-a-live-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "injected-test-model")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    broker.create_draft(
        ACTORS["customer"],
        DraftCreate(idempotency_key=uid("draft"), intent="recent aggregate data"),
    )
    client = InjectedClient(malformed=malformed)
    service = Improvement(broker, model_client=client)
    incidents = service.view(
        ACTORS["controller"], "northwind", "aggregate_regional_market_intelligence"
    )["incidents"]
    request = ImprovementCommand(
        idempotency_key=uid("model"),
        verb="propose",
        customer_id="northwind",
        incident_ids=(incidents[0]["id"],),
        mode="ANTHROPIC",
    )
    result = asyncio.run(service.command(ACTORS["controller"], request))
    assert len(client.calls) == 1
    assert client.calls[0]["tool_choice"] == {"type": "tool", "name": "submit_patches"}
    if malformed:
        assert result["status"] == "FAILED"
        assert service.view(ACTORS["controller"], "northwind", request.product_id)["rejections"]
    else:
        assert result["status"] == "COMPLETE"
        assert result["mode"] == "ANTHROPIC_TEST_DOUBLE"
        assert result["input_tokens"] == 123
        assert (
            service.record(ACTORS["controller"], result["patch_ids"][0])["mode"]
            == "ANTHROPIC_TEST_DOUBLE"
        )
    assert asyncio.run(service.command(ACTORS["controller"], request)) == result
    assert len(client.calls) == 1
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM jf_model_calls").fetchone()[0] == 1
        assert broker.jobflow.available(db)  # Request count is telemetry, not a ceiling.


def test_authorization_expires_even_while_human_review_is_held(broker):
    from tests.broker.conftest import source_bytes

    raw = source_bytes(
        rows=[dict(entity_id="region-001", region_id="R001", value=1, observed_at=None)]
    )
    order = command(broker, accept_order(broker, raw=raw, auth_seconds=900), "provider", "produce")
    broker.clock.advance(600)
    assert broker.view(ACTORS["customer"], order.id).base_order.order.payment_phase == "held"
    broker.clock.advance(300)
    current = broker.view(ACTORS["customer"], order.id)
    assert current.base_order.order.payment_phase == "expired"
    assert not current.base_order.order.ledger


def test_a_dispute_after_capture_never_pretends_base_funds_are_held(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    order = command(broker, order, "customer", "accept_delivery")
    order = command(broker, order, "customer", "dispute", text="Please investigate the date.")
    assert order.base_order.order.payment_phase == "booked"
    broker.clock.advance(600)
    held = broker.view(ACTORS["customer"], order.id)
    assert held.base_order.order.order_state == "human_review"
    assert held.base_order.order.payment_phase == "booked"
    assert len(held.base_order.order.ledger) == 1


def test_paid_case_can_resolve_without_renewing_expired_capture_authority(broker):
    order = command(broker, accept_order(broker, auth_seconds=300), "provider", "produce")
    order = command(broker, order, "customer", "accept_delivery")
    order = command(broker, order, "customer", "dispute", text="Check the source date.")
    broker.clock.advance(600)
    order = broker.view(ACTORS["customer"], order.id)
    task = order.human_tasks[0]
    order = command(
        broker,
        order,
        "controller",
        "resolve_human",
        task_id=task.id,
        decision="RESUME",
        text="Recheck the actual accepted source; no new money is authorized.",
    )
    assert order.human_tasks[0].state == "RESOLVED"
    order = command(broker, order, "customer", "accept_delivery")
    assert order.base_order.order.payment_phase == "booked"
    assert len(order.base_order.order.ledger) == 1
