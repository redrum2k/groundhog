"""Offline payment queue contention, audit cadence and restart fairness."""

from datetime import UTC, datetime, timedelta

import pytest

from app.payments.executor import FakeChainTransport, PaymentExecutor
from app.payments.journal import ACTIVE_TURNS_PER_AUDIT, AUDIT_INTERVAL_SECONDS, PaymentJournal
from tests.payments.test_journal import account, observed, reserve


def history(tmp_path, count=5):
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    chain = FakeChainTransport()
    executor = PaymentExecutor(journal, chain)
    operations = []
    for index in range(count):
        payment = account(f"old-{index}")
        operation = reserve(journal, payment)
        submitted = executor.run_one(operation.operation_id, broadcast=True)
        chain.observations[submitted.transaction_hash] = observed(operation, payment)
        operations.append(executor.run_one(operation.operation_id))
    # Complete one routine audit, then make the historical receipts due again.
    executor.run_one(operations[-1].operation_id)
    with journal.transaction() as db:
        for index, operation in enumerate(operations):
            journal.update(
                db,
                operation.operation_id,
                updated_at=datetime.now(UTC) - timedelta(minutes=5, seconds=count - index),
            )
    return journal, chain, executor, operations


@pytest.mark.parametrize("action", ["fund", "capture", "void"])
def test_active_submission_and_confirmation_precede_old_receipt_backlog(tmp_path, action):
    journal, chain, executor, old = history(tmp_path)
    payment = account("new")
    operation = reserve(journal, payment, action)
    assert executor.run_one(broadcast=True).operation_id == operation.operation_id
    with journal.transaction() as db:
        submitted = journal.get(db, operation.operation_id)
        assert submitted.state == "submitted"
        assert not db.execute(
            "SELECT 1 FROM payment_effects WHERE operation_id=?", (operation.operation_id,)
        ).fetchone()
    chain.observations[submitted.transaction_hash] = observed(operation, payment)
    assert executor.run_one().state == "confirmed"
    with journal.transaction() as db:
        assert journal.get(db, operation.operation_id).state == "confirmed"
        assert (
            db.execute(
                "SELECT count(*) FROM payment_effects WHERE operation_id=?",
                (operation.operation_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            journal.pending(db, limit=1, include_confirmed=True)[0].operation_id
            == old[0].operation_id
        )


def test_audits_are_rate_limited_and_due_at_the_boundary(tmp_path):
    journal, _, executor, old = history(tmp_path, count=1)
    audited = executor.run_one()
    assert audited.operation_id == old[0].operation_id
    with journal.transaction() as db:
        boundary = audited.updated_at + timedelta(seconds=AUDIT_INTERVAL_SECONDS)
        assert not journal.pending(
            db, include_confirmed=True, now=boundary - timedelta(microseconds=1)
        )
        assert journal.pending(db, include_confirmed=True, now=boundary)[0] == audited
    assert executor.run_one() is None


@pytest.mark.parametrize("lost_response", [False, True])
def test_audits_get_a_bounded_share_under_active_load_across_restart(tmp_path, lost_response):
    journal, chain, executor, old = history(tmp_path, count=2)
    active = reserve(journal, account("busy"))
    # An unresolved receipt remains active and yields its turn after every inspection.
    if lost_response:
        chain.broadcast_error = TimeoutError("possibly submitted")
    executor.run_one(active.operation_id, broadcast=True)
    for _ in range(ACTIVE_TURNS_PER_AUDIT - 1):
        assert executor.run_one().operation_id == active.operation_id
    restarted = PaymentExecutor(PaymentJournal(journal.path), chain)
    assert restarted.run_one().operation_id == old[0].operation_id
    assert restarted.run_one().operation_id == active.operation_id
    for _ in range(ACTIVE_TURNS_PER_AUDIT - 1):
        assert restarted.run_one().operation_id == active.operation_id
    assert restarted.run_one().operation_id == old[1].operation_id
    assert len(chain.broadcasts) == 3  # Two historical fundings and one unresolved funding.


def test_batch_selection_interleaves_audit_share_without_mutating_scheduler(tmp_path):
    journal, _, _, old = history(tmp_path, count=1)
    active = [reserve(journal, account(f"active-{index}")) for index in range(10)]
    with journal.transaction() as db:
        selected = journal.pending(db, limit=20, include_confirmed=True)
        assert [item.operation_id for item in selected] == [
            *(item.operation_id for item in active[:ACTIVE_TURNS_PER_AUDIT]),
            old[0].operation_id,
            *(item.operation_id for item in active[ACTIVE_TURNS_PER_AUDIT:]),
        ]
        assert db.execute("SELECT active_turns FROM payment_worker_schedule").fetchone()[0] == 0


def test_active_work_rotates_and_leases_do_not_spend_audit_share(tmp_path):
    journal, chain, executor, _ = history(tmp_path, count=1)
    first = reserve(journal, account("active-a"))
    second = reserve(journal, account("active-b"))
    assert executor.run_one().operation_id == first.operation_id
    assert executor.run_one().operation_id == second.operation_id
    with journal.transaction() as db:
        token = journal.claim(db, first.operation_id)
        assert token
        before = db.execute("SELECT active_turns FROM payment_worker_schedule").fetchone()[0]
        assert journal.claim(db, first.operation_id) is None
        assert (
            db.execute("SELECT active_turns FROM payment_worker_schedule").fetchone()[0] == before
        )
        assert (
            journal.pending(db, limit=1, include_confirmed=True)[0].operation_id
            == second.operation_id
        )
        db.execute(
            "UPDATE payment_operations SET lease_until=0 WHERE operation_id=?",
            (first.operation_id,),
        )
    restarted = PaymentExecutor(PaymentJournal(journal.path), chain)
    assert restarted.run_one().operation_id == first.operation_id


def test_due_audit_still_detects_reorg_without_duplicate_booking(tmp_path):
    journal, chain, executor, old = history(tmp_path, count=1)
    payment = account("old-0")
    chain.observations[old[0].transaction_hash] = observed(old[0], payment, canonical=False)
    assert executor.run_one().state == "orphaned"
    assert executor.run_one() is None
    with journal.transaction() as db:
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 1
    assert len(chain.broadcasts) == 1
