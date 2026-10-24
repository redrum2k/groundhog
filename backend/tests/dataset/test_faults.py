from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.contracts.catalog import Assessment, Provenance
from app.contracts.runs import RunDecision, RunEvidenceAnswer
from app.datasets import produce_dataset, public_bytes
from app.main import create_app
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.runtime.catalog_worker import CatalogWorker
from app.runtime.dataset_policy import cutoff
from tests.dataset.conftest import accepted, delivered, fund
from tests.dataset.test_lifecycle import dispute
from tests.payments.test_catalog_settlement import Journey


def test_one_free_correction_requires_actual_output_defect(dataset_service, monkeypatch):
    s, _ = dataset_service
    original = produce_dataset
    calls = []

    def fault(terms, sources, store):
        calls.append(True)
        csv, preview = original(terms, sources, store)
        if len(calls) == 1:
            raw = (
                b"\n".join(
                    line for line in store.read(csv).splitlines() if not line.startswith(b"94110,")
                )
                + b"\n"
            )
            csv = store.put(raw, "text/csv")
        return csv, preview

    monkeypatch.setattr("app.orders.dataset.produce_dataset", fault)
    order = fund(s, accepted(s))
    worker = CatalogWorker(s)
    assert worker.run_once()
    order = s.get(order.snapshot.order_id)
    assert order.free_corrections_used == 1 and not order.deliveries
    assert worker.run_once()
    order = s.get(order.snapshot.order_id)
    assert len(order.deliveries) == 1 and order.verification.passed
    events = Runs(s).page(order.snapshot.quote.request_id).events
    assert [e.attempt for e in events if e.type == "step_started" and e.step == "produce"] == [1, 2]
    assert any(e.type == "check_failed" and e.attempt == 1 for e in events)
    assert any(e.type == "check_passed" and e.attempt == 2 for e in events)
    s._reserve_correction(order)
    assert order.order_state == "human_review" and order.free_corrections_used == 1


def test_unsafe_artifacts_cannot_be_downloaded(dataset_service):
    s, _ = dataset_service
    order = delivered(s)
    csv = order.deliveries[-1].csv
    unsafe = s.store.put(s.store.read(csv).replace(b",,suppressed", b",42,suppressed"), "text/csv")
    with pytest.raises(DomainError):
        public_bytes(unsafe, s.store)
    assert b",,suppressed" in public_bytes(csv, s.store)


def test_late_production_never_publishes_or_returns_funds(dataset_service, monkeypatch):
    s, clock = dataset_service
    order = fund(s, accepted(s))

    def delayed(terms, sources, store):
        clock.value = cutoff(order) - timedelta(seconds=100)
        return produce_dataset(terms, sources, store)

    monkeypatch.setattr("app.orders.dataset.produce_dataset", delayed)
    CatalogWorker(s).run_once()
    order = s.get(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.deliveries and not order.ledger
    assert order.authorization.receipt is not None


class Unclear:
    def assess_obligation(self, obligation, claim, passages):
        assert passages and all(p.citation.kind == "dataset" for p in passages)
        return Assessment(
            obligation_id=obligation.obligation_id,
            result="UNKNOWN",
            citations=tuple(p.citation for p in passages),
            missing_facts=("Definition evidence",),
            reason_code="NEEDS_DEFINITION",
            explanation="Accepted definition is unresolved.",
            requested_evidence="Which frozen authority establishes yoga membership?",
            provenance=Provenance(kind="model", assessor="injected-test", version="1"),
        )


def test_two_real_answers_no_deadline_extension_and_stale_binding(dataset_service):
    s, _ = dataset_service
    s.investigator = SimpleNamespace(assessor=Unclear())
    order = dispute(s, delivered(s))
    deadline = order.cases[-1].deadline
    worker = CatalogWorker(s)
    worker.run_once()
    api = Runs(s)
    run = order.snapshot.quote.request_id
    order = s.get(order.snapshot.order_id)
    assert order.cases[-1].questions_asked == 1
    before = binding(order)
    for i in range(2):
        api.answer(
            run,
            RunEvidenceAnswer(
                binding=binding(order), text="Please inspect the registered definition."
            ),
            f"answer:{i}",
        )
        updated = api.page(run)
        assert updated.binding.deliveryVersion == before.deliveryVersion
        assert updated.binding.evidenceVersion > before.evidenceVersion
        with pytest.raises(DomainError):
            api.decide(run, RunDecision(action="approve", binding=before), "stale", "reviewer:test")
        worker.run_once()
        order = s.get(order.snapshot.order_id)
    assert order.cases[-1].questions_asked == 2 and order.cases[-1].deadline == deadline
    assert order.order_state == "human_review" and not order.ledger


def test_api_roles_cursor_and_redacted_error(tmp_path):
    app = create_app(
        tmp_path / "db",
        artifact_root=tmp_path / "files",
        run_worker=False,
        internal_token="worker",
        reviewer_token="reviewer",
    )
    with TestClient(app) as client:
        created = client.post("/runs", json={}, headers={"Idempotency-Key": "new"})
        assert created.status_code == 201
        run = created.json()["id"]
        page = client.get(f"/runs/{run}/events")
        assert page.headers["cache-control"] == "no-store"
        assert client.get("/runs/unknown/events").status_code == 404
        assert client.get(f"/runs/{run}/events?after=-1").status_code == 422
        assert client.get(f"/runs/{run}/events?after=9999").status_code == 409
        body = {
            "action": "approve",
            "binding": {
                "runId": run,
                "orderId": "order",
                "snapshotId": "snap",
                "revision": 1,
                "deliveryVersion": 0,
                "evidenceVersion": 1,
            },
        }
        for headers in (
            {"Idempotency-Key": "x"},
            {"Idempotency-Key": "x", "X-Reviewer-Token": "worker"},
        ):
            assert (
                client.post(f"/runs/{run}/decisions", json=body, headers=headers).status_code == 403
            )
        result = client.post(
            "/runs", json={"ending": "secret-never-echo"}, headers={"Idempotency-Key": "bad"}
        )
        assert result.status_code == 422 and "secret-never-echo" not in result.text
        assert (
            client.get(f"/runs/{run}/events").json() == page.json()
            or client.get(f"/runs/{run}/events").json()["events"] == page.json()["events"]
        )


def test_injected_chain_capture_reconciles_after_cutoff(dataset_service):
    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    s = journey.service
    order = accepted(s, payer=journey.buyer.address)
    order, _ = journey.authorize(order)
    s.payments.work()
    order = journey.confirm(order, "fund")
    order = s.run_one(order.snapshot.order_id)
    assert order.deliveries
    order = journey.capture(order)
    assert not order.ledger
    s.payments.work()
    assert journey.operation(order, "capture").state == "submitted"
    clock.value = cutoff(order) + timedelta(seconds=200)
    journey.restart()
    order = journey.confirm(order, "capture")
    assert len(order.ledger) == 1 and order.ledger[0].kind == "capture"
    journey.service.payments.work()
    assert len(journey.current(order).ledger) == 1


def test_integrated_lifespan_runs_broker_sweep_and_improvement_recovery(tmp_path, monkeypatch):
    from threading import Event

    from app.improvement.service import Improvement
    from app.runtime.broker import Broker

    swept, recovered = Event(), Event()
    original_recover = Improvement.recover
    original_expire = Broker.expire_due

    def recover(self):
        result = original_recover(self)
        recovered.set()
        return result

    def expire(self):
        result = original_expire(self)
        swept.set()
        return result

    monkeypatch.setattr(Improvement, "recover", recover)
    monkeypatch.setattr(Broker, "expire_due", expire)
    with TestClient(create_app(tmp_path / "db", artifact_root=tmp_path / "artifacts")) as client:
        assert recovered.wait(2) and swept.wait(2)
        assert client.get("/health").json()["primary_product"] == "aggregate_dataset"
        for profile in ("jobflow", "broker", "improvements"):
            assert client.get(f"/api/{profile}/openapi.json").status_code == 200


def test_replacement_child_waits_for_observed_parent_return(dataset_service):
    from app.contracts.catalog import AcceptQuoteCommand
    from app.contracts.runs import RunOffer
    from tests.dataset.conftest import command

    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    s = journey.service
    parent = accepted(s, payer=journey.buyer.address)
    parent, _ = journey.authorize(parent)
    s.payments.work()
    parent = journey.confirm(parent, "fund")
    parent = s.run_one(parent.snapshot.order_id)
    quote = Runs(s).offer(
        parent.snapshot.quote.request_id,
        RunOffer(binding=binding(parent), scope="replacement"),
        "replacement",
        "provider:test",
    )
    child = s.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="replace-accept"
        )
    )
    assert s.current_view(child.snapshot.order_id).payment.payment.state == "blocked_parent"
    s.payments.work()
    assert journey.operation(parent, "void").state == "submitted"
    with pytest.raises(DomainError):
        s.payments.prepare(child.snapshot.order_id, command(child, "too-soon"))
    assert not child.deliveries and not child.ledger
    journey.confirm(parent, "void")
    page = Runs(s).page(child.snapshot.quote.request_id)
    assert page.payment.payment.state == "awaiting_signature"
    assert any(e.type == "amendment_signed" for e in page.events)
    assert any(
        e.type == "state_changed" and e.paymentState == "awaiting_signature" for e in page.events
    )


def test_late_observed_funding_does_not_dispatch(dataset_service):
    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    s = journey.service
    order = accepted(s, payer=journey.buyer.address)
    order, _ = journey.authorize(order)
    s.payments.work()
    clock.value = cutoff(order) - timedelta(seconds=200)
    order = journey.confirm(order, "fund")
    assert order.order_state == "human_review"
    assert not CatalogWorker(s).run_once()
    assert not order.deliveries and not order.ledger
    assert order.authorization.status == "authorized"
