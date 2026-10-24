from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.contracts.api import Mutation, OpenDispute
from app.contracts.models import InvestigationInput
from app.main import create_app
from app.orders.service import DomainError

WORKER_HEADERS = {"X-Internal-Token": "local-test-worker"}


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def command(order, key, **fields):
    return {
        "expected_revision": order["revision"],
        "expected_binding": order["binding"],
        "idempotency_key": key,
        **fields,
    }


@pytest.fixture
def api(tmp_path, investigation_input):
    clock = Clock(investigation_input.delivery.delivered_at)
    app = create_app(
        tmp_path / "orders.sqlite3",
        internal_token="local-test-worker",
        clock=clock,
        artifact_root=tmp_path / "artifacts",
        run_worker=False,
    )
    with TestClient(app) as client:
        yield client, clock


def create(client, request, *, fee=250, expires_seconds=3600):
    snapshot = request.snapshot.model_dump(mode="json")
    snapshot["policy"]["additional_processing_price"] = (
        {"amount_minor": fee, "currency": "USD", "decimals": 2} if fee else None
    )
    response = client.post(
        "/orders",
        json={
            "snapshot": snapshot,
            "authorization_expires_at": (
                client.app.state.orders.clock() + timedelta(seconds=expires_seconds)
            ).isoformat(),
            "idempotency_key": "create",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["order"]


def publish(client, order, request, key="publish"):
    response = client.post(
        "/internal/orders/order-1/deliveries",
        headers=WORKER_HEADERS,
        json=command(
            order,
            key,
            artifacts=[item.model_dump(mode="json") for item in request.delivery.artifacts],
            structured_data=[
                item.model_dump(mode="json") for item in request.delivery.structured_data
            ],
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()["order"]


def dispute(client, order):
    response = client.post(
        "/orders/order-1/disputes",
        json=command(
            order,
            "dispute",
            complaint="Invoice INV-1 is missing.",
            refund_requested=True,
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()["order"]


def investigate(client, order, result_for, verdict, *, ask=False, key=None):
    request = client.get("/internal/orders/order-1/investigation-input", headers=WORKER_HEADERS)
    assert request.status_code == 200, request.text
    result = result_for(InvestigationInput.model_validate(request.json()), verdict, ask=ask)
    payload = command(
        order, key or f"verdict-{order['revision']}", result=result.model_dump(mode="json")
    )
    return client.post(
        "/internal/orders/order-1/investigations", headers=WORKER_HEADERS, json=payload
    )


def test_open_base_payment_and_poll_contract(api, investigation_input):
    client, _ = api
    order = create(client, investigation_input)
    assert order["payment_phase"] == "open"
    assert order["authorization_receipt"]["status"] == "mock"
    assert order["ledger"] == []
    response = client.get("/orders/order-1")
    assert response.status_code == 200
    assert response.headers["ETag"] == '"1"'
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["poll_after_ms"] == 2000
    assert client.get("/orders/missing").status_code == 404


def test_early_evidenced_verdict_books_only_mock_base(api, investigation_input, result_for):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    response = investigate(client, order, result_for, "compliant")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["display_status"] == "correct"
    assert result["order"]["order_state"] == "closed"
    assert result["order"]["payment_state"] == "mock"
    assert [entry["kind"] for entry in result["order"]["ledger"]] == ["base"]
    assert result["order"]["ledger"][0]["reason"] == "evidence_verdict"
    assert result["order"]["ledger"][0]["receipt"]["status"] == "mock"


def test_cutoff_books_once_without_polling_and_survives_restart(api, investigation_input):
    client, clock = api
    publish(client, create(client, investigation_input), investigation_input)
    clock.advance(599)
    assert client.app.state.orders.expire_due() == 0
    clock.advance(1)
    assert client.app.state.orders.expire_due() == 1
    assert client.app.state.orders.expire_due() == 0
    path = client.app.state.orders.repository.path
    with TestClient(create_app(path, clock=clock, run_worker=False)) as restarted:
        order = restarted.get("/orders/order-1").json()["order"]
        assert len(order["ledger"]) == 1
        assert order["ledger"][0]["reason"] == "review_cutoff"


def test_startup_recovers_missed_deadline(api, investigation_input):
    client, clock = api
    publish(client, create(client, investigation_input), investigation_input)
    clock.advance(601)
    with TestClient(
        create_app(client.app.state.orders.repository.path, clock=clock, run_worker=False)
    ) as restarted:
        assert restarted.get("/orders/order-1").json()["order"]["payment_phase"] == "booked"


def test_unresolved_dispute_at_cutoff_holds_payment(api, investigation_input):
    client, clock = api
    order = publish(client, create(client, investigation_input), investigation_input)
    order = dispute(client, order)
    clock.advance(600)
    assert client.app.state.orders.expire_due() == 1
    response = client.get("/orders/order-1").json()
    assert response["order"]["case_state"] == "human_review"
    assert response["order"]["payment_phase"] == "held"
    assert response["order"]["ledger"] == []
    assert response["available_actions"] == []


def test_refuted_claim_charges_exact_agreed_fee(api, investigation_input, result_for):
    client, _ = api
    order = dispute(
        client, publish(client, create(client, investigation_input), investigation_input)
    )
    response = investigate(client, order, result_for, "compliant", key="resolve")
    assert response.status_code == 200, response.text
    settled = response.json()["order"]
    assert settled["case_state"] == "resolved"
    assert [entry["amount"]["amount_minor"] for entry in settled["ledger"]] == [1000, 250]
    replay = investigate(client, order, result_for, "compliant", key="resolve")
    assert replay.status_code == 200, replay.text
    assert replay.json()["order"] == settled


def test_missing_fee_requires_customer_accepted_quote(api, investigation_input, result_for):
    client, clock = api
    order = dispute(
        client, publish(client, create(client, investigation_input, fee=None), investigation_input)
    )
    response = investigate(client, order, result_for, "compliant")
    assert response.status_code == 200, response.text
    order = response.json()["order"]
    assert order["requires_quote"] is True
    assert len(order["ledger"]) == 1
    quoted = client.post(
        "/internal/orders/order-1/quotes",
        headers=WORKER_HEADERS,
        json=command(
            order,
            "quote",
            amount={"amount_minor": 350, "currency": "USD", "decimals": 2},
            expires_at=(clock() + timedelta(minutes=5)).isoformat(),
        ),
    )
    assert quoted.status_code == 200, quoted.text
    order = quoted.json()["order"]
    assert len(order["ledger"]) == 1
    accepted = client.post(
        "/orders/order-1/quote-acceptance",
        json=command(order, "accept-quote", quote_id=order["quote"]["quote_id"]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["order"]["ledger"][-1]["amount"]["amount_minor"] == 350


def test_supported_claim_regenerates_once_and_repeated_defect_escalates(
    api, investigation_input, result_for
):
    client, _ = api
    order = dispute(
        client, publish(client, create(client, investigation_input), investigation_input)
    )
    response = investigate(client, order, result_for, "provider_defect")
    assert response.status_code == 200, response.text
    order = response.json()["order"]
    assert order["regeneration_pending"] is True
    assert order["free_regenerations_used"] == 1
    assert order["ledger"] == []
    old_binding = order["binding"]
    order = publish(client, order, investigation_input, key="regenerate")
    assert order["binding"]["delivery_version"] == 2
    assert order["binding"] != old_binding
    response = investigate(client, order, result_for, "provider_defect")
    assert response.status_code == 200, response.text
    assert response.json()["order"]["case_state"] == "human_review"
    assert response.json()["order"]["ledger"] == []


def test_operational_failure_is_red_without_fabricated_delivery(api, investigation_input):
    client, _ = api
    order = create(client, investigation_input)
    response = client.post(
        "/internal/orders/order-1/failures",
        headers=WORKER_HEADERS,
        json=command(
            order,
            "failure",
            error_code="engine_failed",
            message="Local fake job failed.",
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_status"] == "operational_failure"
    order = response.json()["order"]
    assert order["deliveries"] == []
    assert order["binding"] is None
    retried = publish(client, order, investigation_input)
    assert retried["binding"]["delivery_version"] == 1


def test_two_answer_rounds_then_human_review(api, investigation_input, result_for):
    client, _ = api
    order = dispute(
        client, publish(client, create(client, investigation_input), investigation_input)
    )
    original_delivery = order["binding"]["delivery_version"]
    original_deadline = order["review_deadline"]
    for index in (1, 2):
        response = investigate(client, order, result_for, "insufficient_evidence", ask=True)
        assert response.status_code == 200, response.text
        order = response.json()["order"]
        assert order["questions_asked"] == index
        answered = client.post(
            "/orders/order-1/answers",
            json=command(
                order,
                f"answer-{index}",
                question_id=order["questions"][0]["question_id"],
                text="Please inspect the supplied source.",
            ),
        )
        assert answered.status_code == 200, answered.text
        order = answered.json()["order"]
        assert order["binding"]["delivery_version"] == original_delivery
        assert order["review_deadline"] == original_deadline
    forbidden = investigate(client, order, result_for, "insufficient_evidence", ask=True)
    assert forbidden.status_code == 422
    response = investigate(client, order, result_for, "insufficient_evidence")
    assert response.status_code == 200, response.text
    assert response.json()["order"]["case_state"] == "human_review"
    assert response.json()["order"]["ledger"] == []


def test_stale_revision_binding_and_idempotency_conflicts(api, investigation_input):
    client, _ = api
    initial = create(client, investigation_input)
    order = publish(client, initial, investigation_input)
    response = client.post("/orders/order-1/acceptance", json=command(initial, "old"))
    assert response.status_code == 409
    payload = command(order, "wrong-binding")
    payload["expected_binding"]["evidence_version"] += 1
    assert client.post("/orders/order-1/acceptance", json=payload).status_code == 409
    fresh = client.get("/orders/order-1").json()["order"]
    accepted = client.post("/orders/order-1/acceptance", json=command(fresh, "accept"))
    assert accepted.status_code == 200, accepted.text
    assert (
        client.post("/orders/order-1/acceptance", json=command(fresh, "accept")).status_code == 200
    )
    assert (
        client.post(
            "/orders/order-1/acceptance", json=command(accepted.json()["order"], "accept")
        ).status_code
        == 409
    )


def test_dispute_capture_race_has_one_winner(api, investigation_input):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    service = client.app.state.orders

    def run(operation, model):
        try:
            return service.mutate("order-1", operation, model).revision
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(run, "accept", Mutation.model_validate(command(order, "accept"))),
            pool.submit(
                run,
                "dispute",
                OpenDispute.model_validate(
                    command(order, "race-dispute", complaint="Missing invoice")
                ),
            ),
        ]
        results = [job.result() for job in jobs]
    assert sorted(results) == [3, 409]
    final = service.get("order-1")
    assert not (final.case_state == "open" and final.ledger)


def test_authorization_expiry_is_separate(api, investigation_input):
    client, clock = api
    publish(client, create(client, investigation_input, expires_seconds=30), investigation_input)
    clock.advance(30)
    order = client.get("/orders/order-1").json()["order"]
    assert order["payment_phase"] == "expired"
    assert order["case_state"] == "human_review"
    assert order["ledger"] == []


def test_customer_cannot_submit_verdicts_or_replace_pdf_arbitrarily(api, investigation_input):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    payload = command(order, "forged", result={})
    assert client.post("/internal/orders/order-1/investigations", json=payload).status_code == 403
    response = client.post(
        "/internal/orders/order-1/deliveries",
        headers=WORKER_HEADERS,
        json=command(
            order,
            "replace",
            artifacts=order["deliveries"][0]["artifacts"],
            structured_data=order["deliveries"][0]["structured_data"],
        ),
    )
    assert response.status_code == 409


def test_customer_answer_evidence_can_be_retrieved_by_exact_version(
    api, investigation_input, result_for
):
    client, _ = api
    order = dispute(
        client, publish(client, create(client, investigation_input), investigation_input)
    )
    question = investigate(client, order, result_for, "insufficient_evidence", ask=True).json()[
        "order"
    ]
    order = client.post(
        "/orders/order-1/answers",
        json=command(
            question,
            "answer",
            question_id="q1",
            text="Invoice INV-1 is the disputed record.",
        ),
    ).json()["order"]
    evidence_id = order["answers"][0]["evidence"]["evidence_id"]
    response = client.get(f"/orders/order-1/evidence/{evidence_id}/content?version=1")
    assert response.status_code == 200
    assert response.json()["text"] == "Invoice INV-1 is the disputed record."
    assert (
        client.get(f"/orders/order-1/evidence/{evidence_id}/content?version=2").status_code == 404
    )


def test_worker_advances_deadline_independently_of_http_reads(tmp_path, investigation_input):
    clock = Clock(investigation_input.delivery.delivered_at)
    app = create_app(tmp_path / "worker.sqlite3", clock=clock, internal_token="local-test-worker")
    with TestClient(app) as client:
        publish(client, create(client, investigation_input), investigation_input)
        completed = Event()
        sweep = app.state.orders.expire_due

        def observe():
            changed = sweep()
            if changed:
                completed.set()
            return changed

        app.state.orders.expire_due = observe
        clock.advance(600)
        assert completed.wait(3), "background worker did not advance the persisted deadline"
        with app.state.orders.repository.transaction() as db:
            persisted = app.state.orders.repository.get(db, "order-1")
        assert len(persisted.ledger) == 1


def test_free_regeneration_engine_failure_escalates(api, investigation_input, result_for):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    order = investigate(client, order, result_for, "provider_defect").json()["order"]
    response = client.post(
        "/internal/orders/order-1/failures",
        headers=WORKER_HEADERS,
        json=command(
            order,
            "regeneration-failed",
            error_code="engine_failed",
            message="Provider unavailable.",
        ),
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["display_status"] == "operational_failure"
    assert view["order"]["case_state"] == "human_review"
    assert len(view["order"]["deliveries"]) == 1
    assert view["order"]["ledger"] == []


def test_dispute_after_early_booking_never_double_charges_base(
    api, investigation_input, result_for
):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    order = investigate(client, order, result_for, "compliant").json()["order"]
    order = dispute(client, order)
    response = investigate(client, order, result_for, "compliant")
    assert response.status_code == 200, response.text
    entries = response.json()["order"]["ledger"]
    assert [entry["kind"] for entry in entries] == ["base", "additional_processing"]


def test_parallel_exact_retries_book_once(api, investigation_input):
    client, _ = api
    order = publish(client, create(client, investigation_input), investigation_input)
    service = client.app.state.orders
    request = Mutation.model_validate(command(order, "same-acceptance"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.mutate, "order-1", "accept", request) for _ in range(2)]
        results = [future.result() for future in futures]
    assert results[0] == results[1]
    assert len(service.get("order-1").ledger) == 1


def test_artifact_resolution_rejects_wrong_hash_and_path_escape(api, investigation_input):
    client, _ = api
    create(client, investigation_input)
    root = client.app.state.artifact_root
    source = investigation_input.snapshot.input_versions[0]
    path = root / source.storage_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not the frozen source bytes")
    assert client.get("/orders/order-1/evidence/input-1/content?version=1").status_code == 409
    path.unlink()
    outside = root.parent / "outside.pdf"
    outside.write_bytes(b"private outside root")
    path.symlink_to(outside)
    assert client.get("/orders/order-1/evidence/input-1/content?version=1").status_code == 404
    assert (
        client.get("/orders/order-1/evidence/expected-answers/content?version=1").status_code == 404
    )
