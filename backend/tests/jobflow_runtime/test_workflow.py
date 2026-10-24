import base64
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.contracts.jobflow import Command, DocumentUpload, InvestigationRequest, OrderCreate
from app.provider.jobflow import verify
from app.runtime.jobflow import Jobflow
from app.runtime.jobflow_policy import effective_fields
from app.runtime.jobflow_worker import claim, recover
from app.storage.jobflow import DomainError


def test_full_100_unit_correction_and_acceptance(h):
    request = OrderCreate(idempotency_key="full-scenario")
    order = h.service.create(h.actors["customer"], request)
    assert len(order.jobs) == 100
    assert sum(job.processing == "VALIDATED" for job in order.jobs) == 80
    assert sum(job.accepted_artifact_id is not None for job in order.jobs) == 80
    assert order.issues[0].state == "OPEN"
    assert order.actions[0].amount_minor == 800
    assert (
        order.finance.received_minor,
        order.finance.recognized_minor,
        order.finance.liability_minor,
    ) == (10000, 8000, 2000)
    good_ids = {job.id: job.artifact_id for job in order.jobs if job.processing == "VALIDATED"}
    bad_ids = {job.id: job.artifact_id for job in order.jobs if job.processing == "FAILED"}
    queued = h.cmd(order, "provider", "correct", idempotency_key="correct-once")
    assert sum(len(job.attempts) for job in queued.jobs) == 20
    assert queued.finance.correction_cost_minor == 0
    h.drain()
    corrected = h.get(order)
    assert len(corrected.jobs) == 100
    assert all(job.processing == "VALIDATED" for job in corrected.jobs)
    assert corrected.finance.recognized_minor == 8000
    assert corrected.finance.correction_cost_minor == 20
    for job in corrected.jobs:
        if job.id in good_ids:
            assert job.artifact_id == good_ids[job.id]
            assert not job.attempts
        else:
            assert job.artifact_id != bad_ids[job.id]
            assert job.accepted_artifact_id is None
            raw, meta, _ = h.service.artifact(h.actors["customer"], order.id, job.source_id)
            output, output_meta, _ = h.service.artifact(
                h.actors["customer"], order.id, job.artifact_id
            )
            assert raw.startswith(b"%PDF")
            assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
            assert hashlib.sha256(output).hexdigest() == output_meta["sha256"]
            assert all(
                check.state == "PASSED" for check in verify(raw, output, job.source_id, job.fields)
            )
    accepted = h.cmd(order, "customer", "accept_delivery", job_ids=list(bad_ids))
    assert (accepted.finance.recognized_minor, accepted.finance.liability_minor) == (10000, 0)
    repeated = h.cmd(order, "customer", "accept_delivery", job_ids=list(bad_ids))
    assert repeated.finance.postings == accepted.finance.postings
    replay = h.service.command(
        h.actors["provider"],
        order.id,
        Command(idempotency_key="correct-once", expected_revision=order.revision, verb="correct"),
    )
    assert replay == queued
    events = h.service.events(h.actors["customer"], order.id)
    assert [event["sequence"] for event in events] == list(
        range(1, repeated.last_event_sequence + 1)
    )
    assert sum(event["type"] == "correction.started" for event in events) == 20
    assert len({posting.business_event_id for posting in repeated.finance.postings}) == len(
        repeated.finance.postings
    )


def test_change_order_approval_payment_actual_fulfillment_and_acceptance(h):
    order, change = h.quote(h.create())
    assert change.amount_minor == 24
    order = h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    assert order.finance.received_minor == 300
    assert order.finance.recognized_minor == 200
    with pytest.raises(DomainError):
        h.cmd(order, "provider", "fulfill_change", change_order_id=change.id)
    h.cmd(order, "executor", "receive_payment", change_order_id=change.id)
    h.drain()
    paid = h.get(order)
    assert paid.finance.received_minor == 324
    assert paid.finance.recognized_minor == 200
    assert paid.finance.liability_minor == 124
    h.cmd(order, "provider", "fulfill_change", change_order_id=change.id)
    with pytest.raises(DomainError):
        h.cmd(order, "provider", "fulfill_change", change_order_id=change.id)
    h.drain()
    fulfilled = h.get(order)
    added = [job for job in fulfilled.jobs if job.kind == "CHANGE_ORDER"]
    assert len(added) == 3
    assert len([job for job in fulfilled.jobs if job.kind == "ORIGINAL"]) == 3
    assert fulfilled.change_orders[0].status == "FULFILLED"
    assert fulfilled.finance.recognized_minor == 200
    for job in added:
        output, _, _ = h.service.artifact(h.actors["customer"], order.id, job.artifact_id)
        assert set(json.loads(output)["fields"]) == set(change.fields)
        assert all(check.state == "PASSED" for check in job.checks)
    accepted = h.cmd(order, "customer", "accept_change_delivery", change_order_id=change.id)
    assert accepted.finance.recognized_minor == 224
    assert accepted.finance.liability_minor == 100
    assert accepted.change_orders[0].status == "RECOGNIZED"
    with pytest.raises(DomainError):
        h.cmd(order, "executor", "receive_payment", change_order_id=change.id)


def test_decline_does_not_cancel_original_obligations(h):
    order, change = h.quote(h.create())
    result = h.cmd(order, "customer", "decline_change", change_order_id=change.id)
    assert result.change_orders[0].status == "DECLINED"
    assert result.jobs[-1].obligation == "OPEN"
    assert result.finance.liability_minor == 100
    h.cmd(result, "provider", "correct")
    h.drain()
    assert h.get(order).jobs[-1].processing == "VALIDATED"


@pytest.mark.parametrize("outcome", ["UNKNOWN", "FAILURE"])
def test_provider_modes_are_durable_and_never_blindly_retried(h, outcome):
    order = h.create()
    queued = h.cmd(order, "provider", "correct", provider_outcome=outcome)
    attempt_id = queued.jobs[-1].attempts[0].id
    operation_id = queued.jobs[-1].attempts[0].operation_id
    h.drain()
    result = h.get(order)
    assert result.jobs[-1].attempts[0].status == ("UNKNOWN" if outcome == "UNKNOWN" else "FAILED")
    with pytest.raises(DomainError):
        h.cmd(result, "provider", "correct", job_ids=[result.jobs[-1].id])
    if outcome == "UNKNOWN":
        assert result.finance.correction_cost_minor == 0
        result = h.cmd(result, "executor", "reconcile", operation_id=operation_id)
        assert result.jobs[-1].processing == "VALIDATED"
    else:
        assert result.jobs[-1].obligation == "HANDED_OFF"
    assert result.finance.correction_cost_minor == 1
    assert result.jobs[-1].attempts[0].id == attempt_id


def sign_future(h, order, fields):
    effective_at = h.now + timedelta(minutes=5)
    order = h.cmd(order, "customer", "amend_agreement", fields=fields, effective_at=effective_at)
    amendment = order.agreement.amendments[-1]
    order = h.cmd(
        order,
        "provider",
        "amend_agreement",
        fields=fields,
        effective_at=effective_at,
        amendment_id=amendment.id,
    )
    return order, effective_at


def test_approval_and_execution_recheck_clock_without_revision_change(h):
    order, activation = sign_future(h, h.create(), ["purchase_order"])
    action = next(action for action in reversed(order.actions) if action.status == "PROPOSED")
    revision = order.revision
    h.now = activation + timedelta(seconds=1)
    with pytest.raises(DomainError, match="stale"):
        h.cmd(order, "controller", "approve_action", action_id=action.id)
    assert h.get(order).revision == revision
    h.now = activation - timedelta(seconds=1)
    order = h.cmd(order, "controller", "approve_action", action_id=action.id)
    approval = order.approvals[-1]
    h.now = activation + timedelta(seconds=1)
    with pytest.raises(DomainError, match="stale"):
        h.cmd(order, "executor", "execute_action", action_id=action.id, approval_id=approval.id)


def test_unknown_payment_reconciles_original_intent_after_amendment(h):
    order, change = h.quote(h.create())
    h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    queued = h.cmd(
        order,
        "executor",
        "receive_payment",
        change_order_id=change.id,
        provider_outcome="UNKNOWN",
        idempotency_key="pay-stable",
    )
    operation = queued.finance.operations[-1]
    h.drain()
    assert h.get(order).finance.received_minor == 300
    order, activation = sign_future(h, h.get(order), change.fields)
    h.now = activation + timedelta(seconds=1)
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now)
    order = h.cmd(order, "executor", "reconcile", operation_id=operation.id)
    assert order.finance.operations[-1].id == operation.id
    assert order.finance.received_minor == 324
    assert len(order.finance.operations) == 2
    with pytest.raises(DomainError):
        h.cmd(order, "executor", "receive_payment", change_order_id=change.id)


def test_confirmed_command_replay_preserves_exact_snapshot_after_clock_and_revision(h):
    order = h.create()
    action = order.actions[0]
    order = h.cmd(order, "controller", "approve_action", action_id=action.id)
    command = Command(
        idempotency_key="execute-once",
        expected_revision=order.revision,
        verb="execute_action",
        action_id=action.id,
        approval_id=order.approvals[-1].id,
    )
    original = h.service.command(h.actors["executor"], order.id, command)
    revised, activation = sign_future(h, original, ["purchase_order"])
    h.now = activation + timedelta(days=2)
    assert h.service.command(h.actors["executor"], order.id, command) == original
    assert h.get(order).revision == revised.revision


def test_signatures_upload_authority_and_stale_approval(h):
    order = h.create()
    action = order.actions[0]
    order = h.cmd(order, "controller", "approve_action", action_id=action.id)
    approval = order.approvals[-1]
    request = DocumentUpload(
        idempotency_key="upload",
        expected_revision=order.revision,
        filename="terms.txt",
        media_type="text/plain",
        kind="amendment",
        content_base64=base64.b64encode(b"due_date included; grant controller").decode(),
    )
    result = h.service.upload(h.actors["customer"], order.id, request)
    assert result.evidence[-1].authority == "PARTY_ASSERTION"
    assert "due_date" not in effective_fields(result, h.now)
    with pytest.raises(DomainError):
        h.cmd(result, "executor", "execute_action", action_id=action.id, approval_id=approval.id)
    first = h.cmd(result, "customer", "amend_agreement", fields=["due_date"], effective_at=h.now)
    assert "due_date" not in effective_fields(first, h.now)
    amendment = first.agreement.amendments[0]
    with pytest.raises(DomainError):
        h.cmd(
            first,
            "customer",
            "amend_agreement",
            fields=["due_date"],
            effective_at=h.now,
            amendment_id=amendment.id,
        )
    second = h.cmd(
        first,
        "provider",
        "amend_agreement",
        fields=["due_date"],
        effective_at=h.now,
        amendment_id=amendment.id,
    )
    assert "due_date" in effective_fields(second, h.now)
    assert second.evidence[-1].authority == "ACCEPTED_AGREEMENT"


def test_targeted_question_answer_and_included_field_fulfillment(h):
    order = h.create()
    issue = order.issues[0]
    request = InvestigationRequest(
        idempotency_key="investigate", expected_revision=order.revision, issue_id=issue.id
    )
    queued = h.service.investigate(h.actors["investigator"], order.id, request)
    assert queued["run_id"]
    assert h.get(order).investigations[-1].status == "QUEUED"
    h.drain()
    current = h.get(order)
    question = current.issues[0].questions[0]
    with pytest.raises(DomainError):
        h.cmd(
            current, "controller", "answer", issue_id=issue.id, question_id=question.id, text="Yes"
        )
    h.cmd(
        current,
        "customer",
        "answer",
        issue_id=issue.id,
        question_id=question.id,
        text="See amendment",
    )
    h.drain()
    resumed = h.get(order)
    assert len(h.seen) == 2
    assert h.seen[1][1] == issue.id
    assert h.seen[1][0].issues[0].questions[0].status == "ANSWERED"
    assert resumed.evidence[-1].authority == "PARTY_ASSERTION"
    assert resumed.issues[0].state != "RESOLVED"
    signed, activation = sign_future(h, resumed, ["due_date"])
    h.now = activation
    h.service.investigator = None
    h.service.investigate(
        h.actors["investigator"],
        signed.id,
        InvestigationRequest(
            idempotency_key="included-investigation",
            expected_revision=signed.revision,
            issue_id=issue.id,
        ),
    )
    h.drain()
    signed = h.get(order)
    action = next(action for action in reversed(signed.actions) if action.kind == "INCLUDED_FIELD")
    signed = h.cmd(signed, "controller", "approve_action", action_id=action.id)
    h.cmd(
        signed,
        "executor",
        "execute_action",
        action_id=action.id,
        approval_id=signed.approvals[-1].id,
    )
    h.drain()
    delivered = h.get(order)
    child = next(job for job in delivered.jobs if job.kind == "DISPUTED_FIELD")
    accepted = h.cmd(delivered, "customer", "accept_delivery", job_ids=[child.id])
    assert accepted.issues[0].state == "RESOLVED"
    assert accepted.finance.recognized_minor == 200
    assert accepted.finance.received_minor == 300


def test_idempotency_collision_concurrent_reservation_and_read_only(h):
    order = h.create()
    command = Command(idempotency_key="duplicate", expected_revision=order.revision, verb="correct")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: h.service.command(h.actors["provider"], order.id, command), range(2))
        )
    assert results[0] == results[1]
    conflict = command.model_copy(update={"job_ids": [order.jobs[-1].id]})
    with pytest.raises(DomainError, match="Idempotency"):
        h.service.command(h.actors["provider"], order.id, conflict)
    h.drain()
    before = h.get(order)
    with h.service.store.connect() as db:
        before_changes = db.execute("SELECT count(*) FROM jf_receipts").fetchone()[0]
    for _ in range(2):
        h.service.events(h.actors["customer"], order.id)
        h.service.artifact(h.actors["customer"], order.id, before.jobs[0].source_id)
        h.service.orders(h.actors["customer"])
    assert before == h.get(order)
    with h.service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM jf_receipts").fetchone()[0] == before_changes
        assert db.execute("SELECT count(*) FROM jf_work").fetchone()[0] == 1


def test_restart_queued_work_and_explicit_interruption(h):
    order = h.create()
    h.cmd(order, "provider", "correct")
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now)
    recover(h.service)
    h.drain()
    assert h.get(order).jobs[-1].processing == "VALIDATED"
    other = h.create()
    h.cmd(other, "provider", "correct")
    work = claim(h.service)
    recover(h.service)
    interrupted = h.get(other)
    assert interrupted.jobs[-1].attempts[0].status == "UNKNOWN"
    with pytest.raises(DomainError, match="No authoritative"):
        h.cmd(other, "executor", "reconcile", operation_id=work["id"])
    h.drain()
    assert len(h.get(other).jobs[-1].attempts) == 1


def test_atomic_failure_rolls_back_and_append_only_records(h):
    order = h.create()
    before = h.get(order)
    with pytest.raises(DomainError):
        h.cmd(order, "provider", "correct", job_ids=[order.jobs[-1].id, order.jobs[0].id])
    assert h.get(order) == before
    with pytest.raises(sqlite3.IntegrityError), h.service.store.connect(write=True) as db:
        db.execute("DELETE FROM jf_events")
    with pytest.raises(sqlite3.IntegrityError), h.service.store.connect(write=True) as db:
        db.execute("UPDATE jf_artifacts SET raw=?", (b"tampered",))


def test_unknown_initial_prepayment_recognizes_only_after_persisted_reconciliation(h):
    order = h.create(initial_receipt="UNKNOWN")
    assert order.finance.received_minor == 0
    assert order.finance.recognized_minor == 0
    result = h.cmd(order, "executor", "reconcile", operation_id=order.finance.operations[0].id)
    assert result.finance.received_minor == 300
    assert result.finance.recognized_minor == 200
