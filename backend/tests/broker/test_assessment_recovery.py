"""Regression evidence for amendment fulfillment and acknowledged dispatch recovery."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.contracts.broker import BrokerCommand
from app.data_products import source_pin
from app.main import create_app
from app.runtime import dispute_assessment
from app.runtime.broker import Broker
from app.storage.jobflow import uid
from tests.broker.conftest import ACTORS, accept_order, command, source_bytes
from tests.broker.test_acceptance_v5 import amend
from tests.broker.test_dispute_assessment import AGE, Assessor, opened, upload_new_version


@pytest.mark.parametrize("enabled,legacy_resolved", [(False, False), (True, False), (True, True)])
def test_no_remedy_fulfills_effective_mutually_accepted_amendment(
    broker, monkeypatch, enabled, legacy_resolved
):
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
    if legacy_resolved:
        # Recreate a pre-fix resolved record without altering bytes or the assessor.
        with monkeypatch.context() as patch:
            patch.setattr(broker, "_fulfill_verified_scope", lambda base: None)
            command(broker, order, "investigator", "investigate")
        assert (
            not broker.view(ACTORS["customer"], order.id)
            .base_order.order.scope_obligations[0]
            .fulfilled
        )
    command(broker, order, "investigator", "investigate")
    current = broker.view(ACTORS["customer"], order.id)
    base = current.base_order.order
    assert current.resolution == "NO_REMEDY" and base.data_verification.verdict == "PASS"
    assert base.scope_obligations[0].fulfilled
    assert base.snapshot == snapshot and base.review_deadline == deadline
    assert not base.ledger and base.free_regenerations_used == 1
    assert len(broker.dispute_assessor.calls) == int(enabled)
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


def work_row(broker):
    with broker.store.connect() as db:
        return dict(db.execute("SELECT * FROM br_assessment_work").fetchone())


def test_receipt_failure_rolls_back_pending_work_and_verification(broker, monkeypatch):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order = opened(broker)
    request = BrokerCommand(
        idempotency_key=uid("atomic"), expected_revision=order.revision, verb="investigate"
    )

    def fail_receipt(*args, **kwargs):
        raise RuntimeError("synthetic receipt failure")

    with monkeypatch.context() as patch:
        patch.setattr(broker.store, "receipt", fail_receipt)
        with pytest.raises(RuntimeError, match="receipt failure"):
            broker.command(ACTORS["investigator"], order.id, request)
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM br_assessment_work").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM br_assessment_attempts").fetchone()[0] == 0
    assert broker.view(ACTORS["customer"], order.id).revision == order.revision
    broker.command(ACTORS["investigator"], order.id, request)
    assert len(assessor.calls) == 1 and work_row(broker)["status"] == "COMPLETE"


@pytest.mark.parametrize("saved_raw", [False, True])
def test_uncertain_dispatch_is_never_retried_by_replay_or_worker(broker, saved_raw):
    def crash(payload, sink):
        if saved_raw:
            sink({"model": "TEST_DOUBLE", "partial": True})
        raise CrashBeforeDispatch  # Process interruption, not a known provider failure.

    assessor = Assessor(crash)
    broker.dispute_assessor = assessor
    order = opened(broker)
    request = BrokerCommand(
        idempotency_key=uid("uncertain"), expected_revision=order.revision, verb="investigate"
    )
    with pytest.raises(CrashBeforeDispatch):
        broker.command(ACTORS["investigator"], order.id, request)
    assert work_row(broker)["status"] == "DISPATCHED"
    restarted = Broker(broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=True)
    assert restarted.recover_assessments() == 0
    restarted.command(ACTORS["investigator"], order.id, request)
    assert len(assessor.calls) == 1
    with broker.store.connect() as db:
        attempt = db.execute("SELECT * FROM br_assessment_attempts").fetchone()
        assert attempt["status"] == "DISPATCHED"
        assert bool(attempt["raw_response_json"]) == saved_raw
    current = restarted.view(ACTORS["customer"], order.id).base_order.order
    assert not current.ledger and current.payment_phase == "held"
    assert current.free_regenerations_used == 0


def test_replay_racing_two_recovery_workers_dispatches_once(broker, monkeypatch):
    entered, release = Event(), Event()

    def delayed(payload, sink):
        entered.set()
        assert release.wait(5)
        return Assessor().assess(payload, sink)

    assessor = Assessor(delayed)
    broker.dispute_assessor = assessor
    order, request, receipt = interrupted_command(broker, monkeypatch)
    worker = Broker(broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(worker.recover_assessments)
        try:
            assert entered.wait(5)
            other = Broker(
                broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=True
            )
            assert other.recover_assessments() == 0
            assert (
                other.command(ACTORS["investigator"], order.id, request).model_dump(mode="json")
                == receipt
            )
        finally:
            release.set()
        assert pending.result(timeout=5) == 1
    assert len(assessor.calls) == 1 and work_row(broker)["status"] == "COMPLETE"


@pytest.mark.parametrize("clock", ["review_deadline", "authorization_expires_at", "overall"])
def test_expired_pending_work_is_cancelled_without_a_call(broker, monkeypatch, clock):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order, _, _ = interrupted_command(broker, monkeypatch)
    original = broker.view(ACTORS["customer"], order.id)
    broker.clock.now = (
        original.overall_case_deadline
        if clock == "overall"
        else getattr(original.base_order.order, clock)
    )
    assert broker.recover_assessments() == 1
    assert work_row(broker)["status"] == "CANCELLED" and not assessor.calls
    with broker.store.connect() as db:
        base = broker.base.repository.get(db, order.id)
        assert base.snapshot == original.base_order.order.snapshot
        assert base.review_deadline == original.base_order.order.review_deadline
        assert not base.ledger and base.free_regenerations_used == 0


def test_changed_evidence_invalidates_pending_work_without_automatic_new_work(broker, monkeypatch):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order, _, _ = interrupted_command(broker, monkeypatch)
    upload_new_version(broker, order.id)
    assert broker.recover_assessments() == 1
    assert work_row(broker)["status"] == "CANCELLED" and not assessor.calls
    assert broker.recover_assessments() == 0


def test_disabled_feature_and_reads_do_not_dispatch_pending_work(broker, monkeypatch):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order, _, _ = interrupted_command(broker, monkeypatch)
    restarted = Broker(broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=False)
    assert restarted.recover_assessments() == 0
    restarted.view(ACTORS["customer"], order.id)
    restarted.events(ACTORS["customer"], order.id)
    assert work_row(broker)["status"] == "PENDING" and not assessor.calls
    restarted.dispute_assessment_enabled = True
    assert restarted.recover_assessments() == 1 and len(assessor.calls) == 1


@pytest.mark.parametrize("uncertain", [False, True])
def test_explicit_legacy_receipt_replay_recovers_gap_but_not_uncertain_attempt(
    broker, monkeypatch, uncertain
):
    if uncertain:

        def crash(payload, sink):
            raise CrashBeforeDispatch

        assessor = Assessor(crash)
        broker.dispute_assessor = assessor
        order = opened(broker)
        request = BrokerCommand(
            idempotency_key=uid("old-uncertain"),
            expected_revision=order.revision,
            verb="investigate",
        )
        with pytest.raises(CrashBeforeDispatch):
            broker.command(ACTORS["investigator"], order.id, request)
    else:
        assessor = Assessor()
        broker.dispute_assessor = assessor
        order, request, _ = interrupted_command(broker, monkeypatch)
    with broker.store.connect(write=True) as db:
        # Only a temporary test DB: simulate a receipt created before the outbox existed.
        db.execute("DELETE FROM br_assessment_work")
        receipt = broker.store.replay(
            db,
            ACTORS["investigator"].id,
            request.idempotency_key,
            {"route": "broker.command", "id": order.id, "body": request.model_dump(mode="json")},
        )
    restarted = Broker(broker.jobflow, dispute_assessor=assessor, dispute_assessment_enabled=True)
    assert restarted.recover_assessments() == 0  # No mass reinterpretation of old receipts.
    replay = restarted.command(ACTORS["investigator"], order.id, request)
    assert replay.model_dump(mode="json") == receipt
    assert len(assessor.calls) == 1
    assert work_row(restarted)["status"] == ("DEDUPLICATED" if uncertain else "COMPLETE")


def test_old_receipt_cannot_authorize_assessment_of_changed_evidence(broker, monkeypatch):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order, request, receipt = interrupted_command(broker, monkeypatch)
    with broker.store.connect(write=True) as db:
        db.execute("DELETE FROM br_assessment_work")  # Temporary pre-outbox fixture only.
    upload_new_version(broker, order.id)
    assert (
        broker.command(ACTORS["investigator"], order.id, request).model_dump(mode="json") == receipt
    )
    assert not assessor.calls and broker.recover_assessments() == 0
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM br_assessment_work").fetchone()[0] == 0


def test_enabling_feature_does_not_reinterpret_completed_deterministic_receipt(broker):
    assessor = Assessor()
    broker.dispute_assessor = assessor
    order = opened(broker)
    broker.dispute_assessment_enabled = False
    order = upload_new_version(broker, order.id)
    changed = order.original_specification.model_copy(
        update={"version": 2, "sources": (source_pin(source_bytes(version=2)),)}
    )
    order = amend(broker, order, changed, broker.clock())
    request = BrokerCommand(
        idempotency_key=uid("rules-receipt"), expected_revision=order.revision, verb="investigate"
    )
    receipt = broker.command(ACTORS["investigator"], order.id, request)
    assert receipt.base_order.order.regeneration_pending
    assert receipt.base_order.order.data_verification.verdict == "FAIL"
    broker.dispute_assessment_enabled = True
    assert broker.command(ACTORS["investigator"], order.id, request) == receipt
    assert not assessor.calls  # Enabling a feature cannot change a completed command's effects.
    current = broker.view(ACTORS["customer"], order.id)
    assert current.base_order.order.regeneration_pending and not current.base_order.order.ledger


def test_enabling_feature_does_not_replace_an_acknowledged_evidence_question(broker, monkeypatch):
    broker.dispute_assessment_enabled = False
    assessor = Assessor()
    broker.dispute_assessor = assessor
    raw = source_bytes(
        rows=[dict(entity_id="region-001", region_id="R001", value=95000, observed_at=None)]
    )
    order = accept_order(broker, raw=raw)
    with monkeypatch.context() as patch:
        patch.setattr(broker, "_verify", lambda db, record, base, *a, **kw: base)
        order = command(broker, order, "provider", "produce")
    order = command(broker, order, "customer", "dispute", text=AGE)
    request = BrokerCommand(
        idempotency_key=uid("rules-question"), expected_revision=order.revision, verb="investigate"
    )
    receipt = broker.command(ACTORS["investigator"], order.id, request)
    assert receipt.base_order.order.data_verification.verdict == "UNKNOWN"
    assert any(q.status == "OPEN" for q in receipt.questions)
    broker.dispute_assessment_enabled = True
    assert broker.command(ACTORS["investigator"], order.id, request) == receipt
    assert not assessor.calls
    assert broker.view(ACTORS["customer"], order.id).questions == receipt.questions
