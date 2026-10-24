"""Combined application, actual Base transport, synthetic RPC/PDFs and no network."""

import base64
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient

from app.agents.compiler import OfflineCompiler
from app.contracts.catalog import RequestDraft, RevisionCommand
from app.main import create_app
from app.orders.service import DomainError
from app.payments import catalog_payment_setup
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig
from tests.payments.test_base_transport import BUYER_KEY, OfflineRpc, offline_config
from tests.payments.test_catalog_settlement import Journey
from tests.payments.test_journal import observed
from tests.runtime.test_catalog_worker import request


def post(client, path, body, status=200, **kwargs):
    response = client.post(path, json=body, **kwargs)
    assert response.status_code == status, response.text
    return response.json()


def poll(client, path, predicate):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        response = client.get(path)
        assert response.status_code == 200, response.text
        value = response.json()
        if predicate(value):
            return value
        time.sleep(0.02)
    pytest.fail(f"transition did not complete: {path}: {value}")


def command(view, key, **fields):
    return {
        "expected_revision": view["order"]["revision"],
        "expected_binding": view["order"]["binding"],
        "idempotency_key": key,
        **fields,
    }


class DelayedRpc(OfflineRpc):
    """Accept synthetic sends but hold receipts until the test releases them."""

    receipts_visible = False
    visible_receipts = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = Event()

    def request(self, method, params):
        if (
            method == "eth_getTransactionReceipt"
            and not self.receipts_visible
            and params[0] not in self.visible_receipts
        ):
            return None
        result = super().request(method, params)
        if method == "eth_sendRawTransaction":
            self.sent.set()
        return result


@pytest.mark.parametrize("mode", ["mock", "base_sepolia"])
@pytest.mark.parametrize("scenario", ["repaired", "unresolved"])
def test_http_automatic_repair_and_settlement_with_restart(setup, mode, scenario):
    original, clock, fixtures = setup
    rpc = DelayedRpc(timestamp=int(clock().timestamp()))
    config = offline_config(original.store.root / "unused-lab.sqlite3", signing=True)
    transport = BasePaymentTransport(config, rpc=rpc)

    def application():
        return create_app(
            original.repository.path,
            artifact_root=original.store.root,
            clock=clock,
            compiler=OfflineCompiler(),
            internal_token="synthetic-worker",
            reviewer_token="synthetic-reviewer",
            payment_mode=mode,
            payment_config=config if mode == "base_sepolia" else None,
            payment_transport=transport if mode == "base_sepolia" else None,
        )

    with TestClient(application()) as client:
        health = client.get("/health").json()
        assert health["live_adapter"] == ("ready" if mode == "base_sepolia" else "disabled")
        assert health["live_settlement_enabled"] == (mode == "base_sepolia")
        draft = post(
            client,
            "/requests",
            {
                "prompt": "Find storage products under 2 kg and unit price at most USD 40.",
                "corpus_id": "storage-2026",
                "idempotency_key": "request",
            },
            201,
        )
        request_path = "/requests/" + draft["request_id"]
        draft = poll(client, request_path, lambda d: d["status"] == "clarification")
        deadline = draft["deadline"]
        post(
            client,
            request_path + "/answers",
            {
                "expected_revision": draft["revision"],
                "idempotency_key": "clarify",
                "question_id": draft["question"]["question_id"],
                "text": "Use net unit weight.",
            },
        )
        draft = poll(client, request_path, lambda d: d["status"] == "ready")
        assert draft["deadline"] == deadline
        quote = post(
            client,
            request_path + "/quotes",
            {
                "expected_revision": draft["revision"],
                "idempotency_key": "quote",
                "payer": Account.from_key(BUYER_KEY).address,
            },
        )
        view = post(
            client,
            "/quote-acceptance",
            {
                "quote_id": quote["quote_id"],
                "customer_actor": "customer:synthetic",
                "idempotency_key": "accept-quote",
            },
            201,
        )
        path = "/orders/" + view["order"]["snapshot"]["order_id"]
        assert view["order"]["jobs"][0]["attempts"] == 0
        assert "prepare_funding" in view["available_actions"]
        preparation = post(client, path + "/funding-preparation", command(view, "prepare"))
        assert preparation["terms"]["amount_atomic"] == "15000000"
        funding = command(
            view,
            "fund",
            funding_attempt_id=preparation["funding_attempt_id"],
            payment_hash=preparation["terms"]["payment_hash"],
        )
        if mode == "mock":
            funding["simulate"] = True
        else:
            signature = (
                "0x"
                + Account.sign_message(
                    encode_typed_data(full_message=preparation["typed_data"]), BUYER_KEY
                ).signature.hex()
            )
            funding["signature"] = signature
        saved = client.post(path + "/funding-authorizations", json=funding)
        assert saved.status_code == 200, saved.text
        assert saved.content == client.post(path + "/funding-authorizations", json=funding).content
        assert "signature" not in saved.text
        if mode == "base_sepolia":
            waiting = poll(
                client,
                path,
                lambda v: any(op["state"] == "submitted" for op in v["payment"]["operations"]),
            )
            assert waiting["order"]["jobs"][0]["attempts"] == 0
            assert not waiting["order"]["deliveries"] and not waiting["order"]["ledger"]
            # The durable submitted marker precedes the actual send. Restart only
            # after this synthetic send completes; the unsent gap has its own test.
            assert rpc.sent.wait(3)
            assert len(rpc.broadcasts) == 1

    # Reconstruct the application against the same temporary store before confirming.
    rpc.receipts_visible = True
    with TestClient(application()) as client:
        view = poll(client, path, lambda v: v["order"]["order_state"] == "waiting_evidence")
        assert view["payment"]["payment"]["state"] == "funded"
        assert len(view["order"]["jobs"]) == 1
        assert saved.content == client.post(path + "/funding-authorizations", json=funding).content
        post(client, path + "/acceptance", command(view, "too-early"), 409)
        artifact = (
            fixtures["repair"].artifact if scenario == "repaired" else fixtures["unregistered"]
        )
        post(
            client,
            path + "/amendments",
            command(
                view,
                "upload",
                evidence_request_id=view["order"]["evidence_requests"][-1]["request_id"],
                actor="customer:synthetic",
                reason="Readable same-edition copy",
                relationship="replacement_page",
                pdf_base64=base64.b64encode(original.store.read(artifact)).decode(),
            ),
        )
        if scenario == "repaired":
            view = poll(client, path, lambda v: v["order"]["order_state"] == "delivered")
            assert view["order"]["verification"]["passed"]
            assert len(view["order"]["deliveries"]) == 1 and not view["order"]["ledger"]
            pdf = view["order"]["deliveries"][-1]["pdf"]
            response = client.get(path + "/artifacts/" + pdf["artifact_id"])
            assert response.content.startswith(b"%PDF-")
            assert response.headers["content-type"] == "application/pdf"
            if mode == "base_sepolia":
                rpc.visible_receipts = set(rpc.receipts)
                rpc.receipts_visible = False
                accepted = post(client, path + "/acceptance", command(view, "accept"))
                assert accepted["payment"]["payment"]["state"] == "capture_pending"
                pending = poll(
                    client,
                    path,
                    lambda v: any(
                        op["intent"]["action"] == "capture" and op["state"] == "submitted"
                        for op in v["payment"]["operations"]
                    ),
                )
                assert not pending["order"]["ledger"]
                rpc.receipts_visible = True
            else:
                clock.advance(60)
            view = poll(client, path, lambda v: v["payment"]["payment"]["state"] == "captured")
            assert view["order"]["order_state"] == "closed"
            assert [b["kind"] for b in view["order"]["ledger"]] == ["capture"]
        else:
            poll(
                client, path, lambda v: v["order"]["amendments"][-1]["classification"] != "pending"
            )
            clock.advance(120)
            view = poll(client, path, lambda v: v["order"]["order_state"] == "human_review")
            assert view["human_review"] and not view["order"]["ledger"]
            if mode == "base_sepolia":
                rpc.visible_receipts = set(rpc.receipts)
                rpc.receipts_visible = False
                report = view["order"]["verification"] or view["order"]["verification_history"][-1]
                decision = command(
                    view,
                    "release",
                    action="release_authorization",
                    reason="Authority remains unestablished.",
                    supporting_evidence=[report["assessments"][0]["citations"][0]],
                )
                post(
                    client,
                    "/reviewer" + path + "/decisions",
                    decision,
                    403,
                    headers={"X-Reviewer-Token": "synthetic-worker"},
                )
                post(
                    client,
                    "/reviewer" + path + "/decisions",
                    decision,
                    headers={"X-Reviewer-Token": "synthetic-reviewer"},
                )
                pending = poll(
                    client,
                    path,
                    lambda v: any(
                        op["intent"]["action"] == "void" and op["state"] == "submitted"
                        for op in v["payment"]["operations"]
                    ),
                )
                assert not pending["order"]["ledger"]
                rpc.receipts_visible = True
                view = poll(client, path, lambda v: v["payment"]["payment"]["state"] == "voided")
                assert [b["kind"] for b in view["order"]["ledger"]] == ["release"]
        assert len(rpc.broadcasts) == (2 if mode == "base_sepolia" else 0)
        assert client.get("/api/jobflow/openapi.json").status_code == 200
        assert not Path(config.journal_path).exists()


@pytest.mark.parametrize("issue", ["signer", "rpc", "preflight", "disabled", "enabled"])
def test_base_startup_capabilities_fail_closed(tmp_path, issue):
    config = offline_config(tmp_path / "unused.sqlite3", signing=True)
    rpc = OfflineRpc()
    if issue == "signer":
        config = replace(config, operator_private_key=None)
    if issue == "disabled":
        config = replace(config, enable_testnet_broadcast=False)
    if issue == "preflight":
        rpc.collector_escrow = "0x" + "99" * 20
    transport = None if issue == "rpc" else BasePaymentTransport(config, rpc=rpc)
    app = create_app(
        tmp_path / "orders.sqlite3",
        artifact_root=tmp_path / "evidence",
        payment_mode="base_sepolia",
        payment_config=config,
        payment_transport=transport,
        run_worker=False,
    )
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["payment_mode"] == "base_sepolia"
        assert health["live_adapter"] == (
            "ready" if issue in ("disabled", "enabled") else "unavailable"
        )
        assert health["live_settlement_enabled"] == (issue == "enabled")
        assert app.state.orders.payments.config.enable_testnet_broadcast == (issue == "enabled")
        assert app.state.orders.payments.mode == "base_sepolia"
        assert not rpc.broadcasts


def test_selected_base_without_configuration_does_not_become_mock():
    selected = catalog_payment_setup(mode="base_sepolia", config=BasePaymentConfig())
    assert selected.mode == "base_sepolia" and selected.transport is None
    assert selected.capabilities.live_adapter == "unavailable"


def test_base_environment_selection_preserves_invoice_mock_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYMENT_ADAPTER", "base_sepolia")
    monkeypatch.setenv("JOBFLOW_DEMO", "1")
    config = offline_config(tmp_path / "unused.sqlite3", signing=True)
    rpc = OfflineRpc()
    app = create_app(
        tmp_path / "orders.sqlite3",
        artifact_root=tmp_path / "evidence",
        payment_config=config,
        payment_transport=BasePaymentTransport(config, rpc=rpc),
        run_worker=False,
    )
    with TestClient(app) as client:
        assert client.get("/health").json()["payment_mode"] == "base_sepolia"
        token = post(client, "/api/jobflow/sessions", {"actor_id": "customer"})["token"]
        invoice = post(
            client,
            "/api/jobflow/orders",
            {
                "idempotency_key": "invoice-in-base-app",
                "document_count": 1,
                "failed_count": 0,
                "disputed_field": None,
                "requested_fields": [],
            },
            headers={"Authorization": "Bearer " + token},
        )
        receipt = invoice["base_order"]["order"]["authorization_receipt"]
        assert receipt["mode"] == "mock" and receipt["transaction_id"] is None
        assert not rpc.broadcasts


def test_disabled_submission_does_not_starve_other_payment_reconciliation(setup):
    journey = Journey(setup)
    service = journey.service
    first, _ = journey.authorize(journey.accepted("first"))
    service.payments.work(limit=1)
    second, _ = journey.authorize(journey.accepted("second"))
    # The injected business clock makes the second reservation older than the
    # first operation's wall-clock submission, so it is selected first.
    operation = journey.operation(first, "fund")
    journey.chain.observations[operation.transaction_hash] = observed(
        operation, journey.view(first).payment.payment
    )
    journey.chain.is_fake = False
    service.payments.config = replace(journey.config, enable_testnet_broadcast=False)
    for _ in range(3):
        service.payments.work(limit=1)
    assert journey.view(first).payment.payment.state == "funded"
    assert journey.view(second).payment.payment.state == "funding_pending"
    assert len(journey.chain.broadcasts) == 1


def test_import_and_schema_export_do_not_initialize_payments(tmp_path):
    root = Path(__file__).resolve().parents[3]
    script = """
import json, socket
def forbidden(*a, **k):
    raise AssertionError('network attempted during import/schema export')
socket.socket.connect = forbidden
from app.main import create_app
print(json.dumps(create_app().openapi(), sort_keys=True))
"""
    result = subprocess.run(
        [str(root / "backend/.venv/bin/python"), "-c", script],
        cwd=tmp_path,
        env={
            "PAYMENT_ADAPTER": "base_sepolia",
            "BASE_CHAIN_ID": "malformed-unused-at-import",
            "ENABLE_TESTNET_BROADCAST": "true",
        },
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["info"]["version"] == "0.4.0"
    assert list(tmp_path.iterdir()) == []


def test_manual_fifth_compile_fences_inflight_fourth_and_replays(setup):
    service, _, _ = setup
    draft = request(
        service, prompt="storage with net unit weight under 2 kg and price at most USD 40"
    )
    with service.repository.transaction() as db:
        draft.compiler_calls = 3
        service.repository.put(db, "request", draft.request_id, draft)
    started, release = Event(), Event()

    class BlockedCompiler:
        def compile(self, context):
            started.set()
            assert release.wait(5)
            return OfflineCompiler().compile(context)

    service.compiler = BlockedCompiler()
    with ThreadPoolExecutor(1) as executor:
        fourth = executor.submit(
            service.compile_request,
            draft.request_id,
            RevisionCommand(expected_revision=draft.revision, idempotency_key="fourth"),
        )
        try:
            assert started.wait(3)
            current = service.get_request(draft.request_id)
            fifth = RevisionCommand(expected_revision=current.revision, idempotency_key="fifth")
            exhausted = service.compile_request(draft.request_id, fifth)
            assert exhausted.status == "human_review" and exhausted.revision > current.revision
            assert service.compile_request(draft.request_id, fifth) == exhausted
        finally:
            release.set()
        with pytest.raises(DomainError, match="stale compiler result"):
            fourth.result(3)
    with service.repository.transaction() as db:
        current = service.repository.load(db, "request", draft.request_id, RequestDraft)
    assert current.status == "human_review" and current.compiler_calls == 4
