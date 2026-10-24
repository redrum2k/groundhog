import json
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.catalog.fixtures import accepted, cmd, repaired

WORKER = {"X-Internal-Token": "worker-test"}
REVIEWER = {"X-Reviewer-Token": "reviewer-test"}


@pytest.fixture
def api(setup):
    service, clock, fixtures = setup
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=clock,
        internal_token="worker-test",
        reviewer_token="reviewer-test",
        run_worker=False,
    )
    with TestClient(app) as client:
        yield client, service, clock, fixtures


def test_client_cannot_manufacture_authoritative_snapshot(api):
    client, _, _, _ = api
    assert client.post("/orders", json={"snapshot": {"price": 1}}).status_code == 404
    assert (
        client.post(
            "/quote-acceptance",
            json={
                "quote_id": "fake",
                "customer_actor": "a",
                "idempotency_key": "key",
                "snapshot": {},
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/quote-acceptance",
            json={"quote_id": "fake", "customer_actor": "a", "idempotency_key": "key"},
        ).status_code
        == 404
    )


def test_http_request_clarification_quote_acceptance_and_worker_boundary(api):
    client, _, _, _ = api
    assert len(client.get("/corpora").json()["storage-2026"]) == 4
    request = client.post(
        "/requests",
        json={
            "prompt": "Storage products under 2 kg and unit price no more than USD 40",
            "corpus_id": "storage-2026",
            "idempotency_key": "api",
        },
    )
    assert request.status_code == 201
    draft = request.json()
    url = f"/internal/requests/{draft['request_id']}/compile"
    payload = {"expected_revision": draft["revision"], "idempotency_key": "compile"}
    assert client.post(url, json=payload).status_code == 403
    assert client.post(url, json=payload, headers=REVIEWER).status_code == 403
    response = client.post(url, json=payload, headers=WORKER)
    assert response.status_code == 200, response.text
    assert response.json()["question"]["field"] == "weight_concept"


def test_polling_etag_and_stale_actions(api):
    client, service, _, fixtures = api
    order = repaired(service, fixtures)
    url = f"/orders/{order.snapshot.order_id}"
    result = client.get(url)
    assert result.status_code == 200 and result.json()["poll_after_ms"] == 2000
    assert result.headers["ETag"] == f'"{order.revision}"'
    assert result.headers["Cache-Control"] == "no-store"
    stale = cmd(order, "stale").model_dump(mode="json")
    stale["expected_revision"] -= 1
    assert client.post(url + "/acceptance", json=stale).status_code == 409
    response = client.post(url + "/acceptance", json=cmd(order, "accept").model_dump(mode="json"))
    assert response.status_code == 200 and response.json()["order"]["order_state"] == "closed"
    assert len(response.json()["order"]["ledger"]) == 1


def test_historical_artifacts_remain_available_and_unrelated_ids_do_not(api):
    client, service, _, fixtures = api
    order = repaired(service, fixtures)
    original = order.snapshot.quote.sources[1].artifact
    url = f"/orders/{order.snapshot.order_id}/artifacts/"
    response = client.get(url + original.artifact_id)
    assert response.status_code == 200 and response.content == service.store.read(original)
    assert client.get(url + "unregistered-evidence").status_code == 404


def test_reviewer_and_investigator_authority_are_separate(api):
    from app.contracts.catalog import ReviewCommand

    client, service, clock, _ = api
    order = service.run_one(accepted(service).snapshot.order_id)
    clock.advance(120)
    order = service.get(order.snapshot.order_id)
    command = cmd(
        order,
        "decision",
        ReviewCommand,
        action="release_authorization",
        reason="Evidence unavailable.",
        supporting_evidence=(order.verification.assessments[0].citations[0],),
    )
    url = f"/reviewer/orders/{order.snapshot.order_id}/decisions"
    body = command.model_dump(mode="json")
    assert client.post(url, json=body).status_code == 403
    assert client.post(url, json=body, headers=WORKER).status_code == 403
    response = client.post(url, json=body, headers=REVIEWER)
    assert response.status_code == 200, response.text
    assert response.json()["order"]["decisions"][-1]["actor"] == "reviewer:local-trusted"
    assert client.post(url, json={**body, "actor": "forged"}, headers=REVIEWER).status_code == 422


def test_historical_data_access_is_trusted_read_only(api):
    client, service, _, _ = api
    raw = '{"policy":{"seconds":600},"ledger":[{"amount":250}]}'
    with service.repository.transaction() as db:
        db.execute("INSERT INTO orders VALUES (?,?)", ("old", raw))
        db.execute(
            "INSERT INTO order_commands VALUES (?,?,?,?)", ("old", "old-key", "request", raw)
        )
    url = "/reviewer/legacy/orders/old"
    assert client.get(url).status_code == 403
    assert client.get(url, headers=REVIEWER).text == raw
    assert client.get(url + "/commands/old-key", headers=REVIEWER).text == raw
    assert client.post("/orders/old/acceptance", json={}).status_code == 422
    assert client.get("/orders/old").status_code == 404


def test_openapi_has_no_client_price_or_legacy_creation(api):
    client, _, _, _ = api
    schema = client.get("/openapi.json").json()
    assert schema["info"]["version"] == "0.4.0"
    assert "/orders" not in schema["paths"]
    assert "/requests" in schema["paths"]
    policy = schema["components"]["schemas"]["Policy"]["properties"]
    assert policy["review_seconds"]["const"] == 60
    accept = schema["components"]["schemas"]["AcceptQuoteCommand"]
    assert accept["additionalProperties"] is False and "amount" not in accept["properties"]
    assert "additional_processing" not in json.dumps(schema["paths"])
    operations = [
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    ]
    assert len(set(operations)) == len(operations)


def test_background_deadline_sweep_is_independent_of_polling(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    app = create_app(
        service.repository.path, artifact_root=service.store.root, clock=clock, run_worker=True
    )
    with TestClient(app):
        done = Event()
        original = app.state.orders.expire_due

        def sweep():
            changed = original()
            done.set()
            return changed

        app.state.orders.expire_due = sweep
        clock.advance(60)
        assert done.wait(4)
    assert service.get(order.snapshot.order_id).order_state == "closed"
