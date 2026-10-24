"""Exercise Lucas's public contract without wallets, RPCs or paid providers."""

import importlib.util
import json
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient

from app.contracts.catalog import QuoteRequest
from app.contracts.payments import PaymentAccount, PaymentView
from app.main import create_app
from app.orders.service import DomainError
from tests.catalog.fixtures import draft_quote, repaired

WORKER = {"X-Internal-Token": "worker-test"}


@pytest.fixture
def payment_api(setup):
    service, clock, _ = setup
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=clock,
        internal_token="worker-test",
        reviewer_token="reviewer-test",
        run_worker=False,
    )
    with TestClient(app) as client:
        yield client, service, clock


def pending(api, payer=None):
    client, service, _ = api
    draft, quote = draft_quote(service)
    if payer:
        quote = service.issue_quote(
            draft.request_id,
            QuoteRequest(
                expected_revision=draft.revision,
                idempotency_key="wallet-quote",
                payer=payer,
            ),
        )
    body = {
        "quote_id": quote.quote_id,
        "customer_actor": "customer:demo",
        "idempotency_key": "accept-quote",
    }
    response = client.post("/quote-acceptance", json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def command(view, key):
    return {
        "expected_revision": view["order"]["revision"],
        "expected_binding": view["order"]["binding"],
        "idempotency_key": key,
    }


def prepare(client, view):
    url = f"/orders/{view['order']['snapshot']['order_id']}"
    response = client.post(url + "/funding-preparation", json=command(view, "prepare"))
    assert response.status_code == 200, response.text
    return url, response.json()


def test_acceptance_signature_and_mock_confirmation_are_distinct(payment_api):
    client, service, clock = payment_api
    view, accepted_body = pending(payment_api)
    assert view["order"]["schema_version"] == 4
    assert view["order"]["order_state"] == "awaiting_authorization"
    assert view["order"]["authorization"]["receipt"] is None
    assert view["payment"]["payment"]["state"] == "awaiting_signature"
    assert set(view["available_actions"]) == {"prepare_funding", "submit_funding_authorization"}
    url, prepared = prepare(client, view)
    assert prepared["terms"]["amount_atomic"] == "15000000"
    assert prepared["typed_data"]["message"]["value"] == "15000000"
    assert "from" in prepared["typed_data"]["message"]
    assert "from_" not in prepared["typed_data"]["message"]
    assert prepared["typed_data"]["domain"]["name"] == "Mock USDC (no onchain authorization)"
    assert client.post("/internal" + url + "/work", headers=WORKER).status_code == 409
    body = {
        **command(view, "fund"),
        "funding_attempt_id": prepared["funding_attempt_id"],
        "payment_hash": prepared["terms"]["payment_hash"],
        "simulate": True,
    }
    submitted = client.post(url + "/funding-authorizations", json=body)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["payment"]["payment"]["state"] == "funding_pending"
    assert submitted.json()["order"]["order_state"] == "awaiting_authorization"
    assert client.post("/internal/payments/work").status_code == 403
    assert client.post("/internal/payments/work", headers=WORKER).json()["processed"] == 1
    clock.advance(1)
    funded = client.get(url).json()
    assert funded["payment"]["payment"]["state"] == "funded"
    assert funded["payment"]["simulated"] and not funded["payment"]["explorer_links"]
    assert funded["order"]["order_state"] == "processing"
    assert funded["order"]["authorization"]["receipt"]["status"] == "mock"
    assert client.post(url + "/funding-authorizations", json=body).json() == submitted.json()
    assert client.post("/quote-acceptance", json=accepted_body).json() == view
    assert client.post("/internal/payments/work", headers=WORKER).json()["processed"] == 0
    changed = {**body, "payment_hash": "0x" + "00" * 32}
    assert client.post(url + "/funding-authorizations", json=changed).status_code == 409
    assert len(service.get(view["order"]["snapshot"]["order_id"]).jobs) == 1


def test_real_eoa_signature_checked_offline_and_never_public(payment_api):
    client, service, _ = payment_api
    # Fresh disposable test key exists only in this test process.
    buyer = Account.create()
    view, _ = pending(payment_api, buyer.address)
    url, preparation = prepare(client, view)
    signature = (
        "0x"
        + Account.sign_message(
            encode_typed_data(full_message=preparation["typed_data"]),
            buyer.key,
        ).signature.hex()
    )
    body = {
        **command(view, "signed"),
        "funding_attempt_id": preparation["funding_attempt_id"],
        "payment_hash": preparation["terms"]["payment_hash"],
        "signature": signature,
    }
    response = client.post(url + "/funding-authorizations", json=body)
    assert response.status_code == 200, response.text
    assert signature not in response.text
    assert signature not in client.get(url + "/payment").text
    with service.repository.transaction() as db:
        commands = "".join(str(row) for row in db.execute("SELECT * FROM catalog_commands"))
    assert signature not in commands


def test_stale_invalid_and_expired_authorizations_do_not_fund(payment_api):
    client, _, clock = payment_api
    view, _ = pending(payment_api)
    url, preparation = prepare(client, view)
    body = {
        **command(view, "fund"),
        "funding_attempt_id": preparation["funding_attempt_id"],
        "payment_hash": preparation["terms"]["payment_hash"],
        "simulate": True,
    }
    assert (
        client.post(
            url + "/funding-authorizations",
            json={
                **body,
                "expected_revision": 2,
            },
        ).status_code
        == 409
    )
    secret_marker = "signature-must-not-be-echoed"
    invalid = client.post(
        url + "/funding-authorizations",
        json={
            **body,
            "simulate": False,
            "signature": secret_marker,
        },
    )
    assert invalid.status_code == 422 and secret_marker not in invalid.text
    assert invalid.json()["detail"] == "request validation failed"
    assert all("input" not in issue for issue in invalid.json()["issues"])
    clock.advance(181)
    assert client.post(url + "/funding-authorizations", json=body).status_code == 409
    assert client.post("/internal/payments/work", headers=WORKER).json()["processed"] == 0


def test_all_payment_fixture_states_serve_on_frozen_endpoint():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("frontend_mock", root / "tools/frontend_mock.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    states = set(PaymentAccount.model_json_schema()["properties"]["state"]["enum"])
    with TestClient(module.create_mock_app()) as client:
        assert set(client.get("/__mock/states").json()) == states
        for state in states:
            result = client.get(f"/orders/demo/payment?state={state}")
            view = PaymentView.model_validate(result.json())
            assert view.payment.state == state and view.payment.order_id == "demo"
            assert view.simulated and not view.explorer_links
            assert all(op.transaction_hash is None for op in view.operations)
        assert client.get("/orders/demo/payment?state=typo").status_code == 404


def test_unfunded_expiry_removes_actions_and_cannot_book_a_return(payment_api):
    client, service, clock = payment_api
    view, _ = pending(payment_api)
    order_id = view["order"]["snapshot"]["order_id"]
    clock.advance(181)
    expired = client.get(f"/orders/{order_id}").json()
    assert expired["available_actions"] == []
    assert expired["order"]["order_state"] == "human_review"
    assert expired["payment"]["payment"]["state"] == "failed"
    order = service.get(order_id)
    with pytest.raises(DomainError, match="no held funds"):
        service._release(order, clock())
    assert service.get(order_id).ledger == ()
    clock.advance(3600)
    assert service.current_view(order_id).payment.payment.state == "failed"


def test_historical_order_is_read_only_without_new_payment_actions(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    historical = order.model_copy(update={"schema_version": 3, "payment_id": None})
    historical.snapshot = historical.snapshot.model_copy(
        update={
            "schema_version": 3,
            "quote": historical.snapshot.quote.model_copy(update={"payment_terms": None}),
        }
    )
    raw = historical.model_dump_json()
    with service.repository.transaction() as db:
        service.repository.put(db, "order", historical.snapshot.order_id, historical)
    clock.advance(4000)
    view = service.current_view(historical.snapshot.order_id)
    assert view.available_actions == () and view.payment is None
    assert view.order.model_dump_json() == raw


def test_exported_openapi_matches_runtime_and_wallet_schema(payment_api):
    client, _, _ = payment_api
    schema = client.get("/openapi.json").json()
    root = Path(__file__).resolve().parents[3]
    assert schema == json.loads((root / "docs/openapi.json").read_text())
    schemas = schema["components"]["schemas"]
    assert schemas["PaymentTerms"]["properties"]["amount_atomic"]["type"] == "string"
    assert "from" in schemas["AuthorizationMessage"]["properties"]
    assert schema["paths"]["/orders/{order_id}/funding-authorizations"]["post"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("ErrorResponse")
    assert client.get("/health").json()["live_adapter"] == "disabled"
