"""Regression evidence for amendment fulfillment and acknowledged dispatch recovery."""

from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.contracts.broker import BrokerCommand
from app.data_products import source_pin
from app.main import create_app
from app.runtime import dispute_assessment
from app.runtime.broker import Broker
from app.storage.jobflow import uid
from tests.broker.conftest import ACTORS, command, source_bytes
from tests.broker.test_acceptance_v5 import amend
from tests.broker.test_dispute_assessment import AGE, Assessor, opened, upload_new_version


@pytest.mark.parametrize("enabled", [False, True])
def test_no_remedy_fulfills_effective_mutually_accepted_amendment(broker, monkeypatch, enabled):
    broker.dispute_assessor = Assessor()
    order = opened(broker)
    broker.dispute_assessment_enabled = False
    snapshot = order.base_order.order.snapshot
    order = upload_new_version(broker, order.id)
    amended = order.original_specification.model_copy(
        update={"version": 2, "sources": (source_pin(source_bytes(version=2)),)}
    )
    order = amend(broker, order, amended, broker.clock())
    assert not order.base_order.order.scope_obligations[0].fulfilled
    order = command(broker, order, "investigator", "investigate")
    assert order.base_order.order.regeneration_pending
    # Fixture seam: publish real compliant bytes but defer verification. No PASS
    # or fulfilled obligation is injected; investigate must independently earn both.
    with monkeypatch.context() as patch:
        patch.setattr(broker, "_verify", lambda db, record, base, *a, **kw: base)
        order = command(broker, order, "provider", "produce")
    broker.dispute_assessment_enabled = enabled
    order = command(broker, order, "customer", "dispute", text=AGE)
    deadline = order.base_order.order.review_deadline
    command(broker, order, "investigator", "investigate")
    current = broker.view(ACTORS["customer"], order.id)
    base = current.base_order.order
    assert current.resolution == "NO_REMEDY" and base.data_verification.verdict == "PASS"
    assert base.scope_obligations[0].fulfilled
    assert base.snapshot == snapshot and base.review_deadline == deadline
    assert not base.ledger and base.free_regenerations_used == 1
    accepted = command(broker, current, "customer", "accept_delivery")
    assert len(accepted.base_order.order.ledger) == 1
    assert accepted.base_order.order.snapshot == snapshot


class CrashBeforeDispatch(BaseException):
    pass


def interrupted_command(broker, monkeypatch):
    order = opened(broker)
    request = BrokerCommand(
        idempotency_key=uid("acknowledged"), expected_revision=order.revision, verb="investigate"
    )

    def crash(*args, **kwargs):
        raise CrashBeforeDispatch

    with monkeypatch.context() as patch:
        patch.setattr(dispute_assessment, "run_assessment", crash)
        with pytest.raises(CrashBeforeDispatch):
            broker.command(ACTORS["investigator"], order.id, request)
    with broker.store.connect() as db:
        receipt = broker.store.replay(
            db,
            ACTORS["investigator"].id,
            request.idempotency_key,
            {"route": "broker.command", "id": order.id, "body": request.model_dump(mode="json")},
        )
        assert receipt is not None
        assert db.execute("SELECT count(*) FROM br_assessment_attempts").fetchone()[0] == 0
    return order, request, receipt


def test_replay_after_committed_receipt_recovers_only_undispatched_work(broker, monkeypatch):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order, request, receipt = interrupted_command(broker, monkeypatch)
    restarted = Broker(broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=True)
    result = restarted.command(ACTORS["investigator"], order.id, request)
    assert len(assessor.calls) == 1
    assert result.model_dump(mode="json") == receipt
    assert restarted.command(ACTORS["investigator"], order.id, request) == result
    assert len(assessor.calls) == 1
    current = restarted.view(ACTORS["customer"], order.id)
    assert current.resolution == "NO_REMEDY" and not current.base_order.order.ledger


def test_backend_worker_recovers_committed_work_without_client_replay(broker, monkeypatch):
    ready = Event()

    def assessed(payload, sink):
        result = Assessor().assess(payload, sink)
        ready.set()
        return result

    assessor = Assessor(assessed)
    broker.dispute_assessor = assessor
    order, _, _ = interrupted_command(broker, monkeypatch)
    monkeypatch.setenv("ENABLE_BROKER_DISPUTE_ASSESSMENT", "true")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "false")
    monkeypatch.setattr(dispute_assessment, "DisputeAssessor", lambda: assessor)
    with TestClient(create_app(service=broker.jobflow, payment_mode="mock", run_worker=True)):
        assert ready.wait(5), "Acknowledged assessment was not recovered by the backend worker"
    # Lifespan drains the in-flight result before returning.
    assert len(assessor.calls) == 1
    current = broker.view(ACTORS["customer"], order.id)
    assert current.resolution == "NO_REMEDY" and not current.base_order.order.ledger
