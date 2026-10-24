"""Real outbox/transport, synthetic signers/RPC and independently controlled clocks."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from eth_account import Account
from eth_account.signers.local import LocalAccount
from test_base_transport import buyer_signature, lab
from test_payment_lab import invoke

from app.payments import journal as journal_module
from app.payments.attempt import AttemptStopped, PaymentAttempt, current_attempt
from app.payments.base import BasePaymentTransport
from app.payments.journal import PaymentJournal
from app.runtime.background import background_workers

# isort: split
from spikes.payments.offline import BUYER_KEY, OfflineRpc, offline_config
from spikes.payments.reclaim import ReclaimSubmission, stage_reclaim


class Clock:
    elapsed = 0
    lease = 0
    chain = 1000

    def now(self, tz):
        return datetime(2026, 10, 24, tzinfo=UTC) + timedelta(seconds=self.lease)

    def advance(self, seconds):
        self.elapsed += seconds
        self.lease += seconds
        self.chain += seconds

    def attempt(self, seconds=300, **kwargs):
        return PaymentAttempt(seconds, clock=lambda: self.elapsed, **kwargs)


class SlowRpc(OfflineRpc):
    delay = 0
    hook = None

    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def request(self, method, params):
        self.clock.advance(self.delay)
        self.timestamp = self.clock.chain
        if self.hook:
            self.hook(method, params)
        return super().request(method, params)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(journal_module, "datetime", clock)
    monkeypatch.setattr(lab, "PaymentAttempt", clock.attempt)
    config = offline_config(tmp_path / "lab.sqlite3", signing=True)
    journal = PaymentJournal(config.journal_path)
    payment = lab.create_fixture(
        config, "capture-a", Account.from_key(BUYER_KEY).address, 1000, 3600, offline=True
    )
    with journal.transaction() as db:
        journal.create_payment(db, payment)
    rpc = SlowRpc(clock)
    transport = BasePaymentTransport(config, rpc=rpc)
    return clock, journal, payment, rpc, transport


def reserve(rig, action="fund"):
    _, journal, payment, _, _ = rig
    operation = lab.operation_for(payment, action)
    with journal.transaction() as db:
        journal.reserve(
            db, operation, "0x" + buyer_signature(payment.terms).hex() if action == "fund" else None
        )
    return operation


def executor(rig):
    clock, journal, _, _, transport = rig
    result = lab.laboratory_executor(journal, transport)
    result.attempt_factory = clock.attempt
    return result


def assert_unsubmitted(rig, operation, *, state="reserved"):
    _, journal, payment, rpc, _ = rig
    with journal.transaction() as db:
        current = journal.get(db, operation.operation_id)
        assert current.state == state
        assert current.transaction_hash is None
        assert journal.private(db, operation.operation_id)[0] is None
        assert journal.payment(db, payment.payment_id).terms == payment.terms
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
    assert not rpc.broadcasts
    return current


def test_136_second_preparation_renews_with_all_three_clocks_advancing(rig):
    clock, journal, payment, rpc, transport = rig
    operation = reserve(rig)
    prepare = transport.prepare_transaction
    preparation = []

    def measured(*args, **kwargs):
        start = clock.elapsed
        result = prepare(*args, **kwargs)
        preparation.append(clock.elapsed - start)
        return result

    transport.prepare_transaction = measured
    rpc.delay = 4
    result = executor(rig).run_one(operation.operation_id, broadcast=True)
    assert preparation == [128]  # Plus two 4s nonce reads = original 136s leased preparation.
    assert result.state == "submitted" and result.nonce == 0
    assert clock.elapsed == 148 and clock.chain == 1148
    assert len(rpc.broadcasts) == 1
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).terms == payment.terms
        assert db.execute("SELECT lease_token FROM payment_operations").fetchone() == (None,)


def test_lab_preflight_is_in_same_budget_and_financial_window(rig, tmp_path):
    clock, _, _, rpc, _ = rig
    rpc.delay = 4
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 0
    assert clock.elapsed == 256  # 27 initial reads + 34 preparation + 3 send reads.
    assert len(rpc.broadcasts) == 1 and clock.chain == 1256


def test_lab_preflight_does_not_reset_total_budget(rig, tmp_path, monkeypatch):
    clock, journal, _, rpc, _ = rig
    monkeypatch.setattr(lab, "PaymentAttempt", lambda: clock.attempt(180))
    rpc.delay = 4
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 3
    assert 160 <= clock.elapsed < 180
    with journal.transaction() as db:
        operation = journal.operations(db, "capture-a")[0]
    assert assert_unsubmitted(rig, operation).nonce == 0


@pytest.mark.parametrize("stop", ["budget", "cancel", "financial"])
@pytest.mark.parametrize("concurrent_reservation", [False, True])
def test_late_buyer_signature_never_crosses_reservation_boundary(
    rig, tmp_path, monkeypatch, capsys, stop, concurrent_reservation
):
    clock, journal, payment, rpc, transport = rig
    attempt = clock.attempt()
    monkeypatch.setattr(lab, "PaymentAttempt", lambda: attempt)
    sign = LocalAccount.sign_message
    signature = "0x" + buyer_signature(payment.terms).hex()
    signed = transport.prepare_transaction("fund", payment.terms, 0, signature)
    before = []

    def delayed_sign(self, *args, **kwargs):
        result = sign(self, *args, **kwargs)
        if concurrent_reservation:
            # Another owner reserves while this signer is outside the transaction.
            operation = lab.operation_for(payment, "fund")
            with journal.transaction() as db:
                journal.reserve(db, operation, signature)
                journal.reserve_nonce(db, operation.operation_id, signed.sender, 0)
                journal.save_signed(db, operation.operation_id, signed)
                before.append(journal.private(db, operation.operation_id))
        if stop == "cancel":
            attempt.cancelled.set()
        elif stop == "financial":
            # Independent absolute authority advances without exhausting elapsed budget.
            timestamp, started = attempt.chain_anchor
            attempt.chain_anchor = (timestamp + 300, started)
        else:
            clock.elapsed += 301
        return result

    monkeypatch.setattr(LocalAccount, "sign_message", delayed_sign)
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == (2 if stop == "financial" else 3)
    output = capsys.readouterr()
    assert "attempt stopped" in output.err
    assert signature not in output.err + output.out and BUYER_KEY not in output.err + output.out
    with journal.transaction() as db:
        operations = journal.operations(db, payment.payment_id)
        assert len(operations) == int(concurrent_reservation)
        if concurrent_reservation:
            assert operations[0].state == "signed" and operations[0].nonce == 0
            assert journal.private(db, operations[0].operation_id) == before[0]
        assert journal.payment(db, payment.payment_id).terms == payment.terms
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
    assert not rpc.broadcasts


@pytest.mark.parametrize("stop", ["budget", "cancel", "financial"])
@pytest.mark.parametrize("concurrent_reservation", [False, True])
def test_reservation_rechecks_after_waiting_for_sqlite_write_lock(
    rig, tmp_path, monkeypatch, capsys, stop, concurrent_reservation
):
    clock, journal, payment, rpc, transport = rig
    attempt = clock.attempt()
    monkeypatch.setattr(lab, "PaymentAttempt", lambda: attempt)
    signature = "0x" + buyer_signature(payment.terms).hex()
    signed = transport.prepare_transaction("fund", payment.terms, 0, signature)
    sign = LocalAccount.sign_message
    locked, waiting, release = Event(), Event(), Event()
    before = []
    connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "BEGIN IMMEDIATE" and locked.is_set():
                waiting.set()  # Real second connection must wait for the writer below.
            return super().execute(sql, *args, **kwargs)

    def observed_connect(*args, **kwargs):
        return connect(*args, **kwargs, factory=ObservedConnection)

    monkeypatch.setattr(journal_module.sqlite3, "connect", observed_connect)

    def writer():
        with journal.transaction() as db:
            if concurrent_reservation:
                operation = lab.operation_for(payment, "fund")
                journal.reserve(db, operation, signature)
                journal.reserve_nonce(db, operation.operation_id, signed.sender, 0)
                journal.save_signed(db, operation.operation_id, signed)
                before.append(journal.private(db, operation.operation_id))
            locked.set()
            assert release.wait(3)

    def signing(self, *args, **kwargs):
        result = sign(self, *args, **kwargs)
        # Lock acquisition starts only after preflight and before the late write.
        writer_future.append(pool.submit(writer))
        assert locked.wait(3)
        return result

    writer_future = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        monkeypatch.setattr(LocalAccount, "sign_message", signing)
        future = pool.submit(invoke, tmp_path, "fund", "--simulate", rpc=rpc)
        try:
            assert waiting.wait(3)
            if stop == "cancel":
                attempt.cancelled.set()
            elif stop == "financial":
                timestamp, started = attempt.chain_anchor
                attempt.chain_anchor = (timestamp + 300, started)
            else:
                clock.elapsed += 301
        finally:
            release.set()
        assert future.result(timeout=3) == (2 if stop == "financial" else 3)
        writer_future[0].result(timeout=3)
    assert "attempt stopped" in capsys.readouterr().err
    with journal.transaction() as db:
        operations = journal.operations(db, payment.payment_id)
        assert len(operations) == int(concurrent_reservation)
        if concurrent_reservation:
            assert operations[0].state == "signed" and operations[0].nonce == 0
            assert journal.private(db, operations[0].operation_id) == before[0]
        assert journal.payment(db, payment.payment_id).terms == payment.terms
    assert not rpc.broadcasts


@pytest.mark.parametrize("offset", [120, 121])
def test_renewal_boundary_tokens_successor_and_activity(rig, offset):
    clock, journal, _, _, _ = rig
    operation = reserve(rig)
    other = PaymentJournal(journal.path)
    with journal.transaction() as db:
        token = journal.claim(db, operation.operation_id)
        before = db.execute("SELECT lease_token,lease_until FROM payment_operations").fetchone()
        assert not journal.renew_claim(db, operation.operation_id, "wrong")
        assert not journal.renew_claim(db, "missing", token)
        assert (
            db.execute("SELECT lease_token,lease_until FROM payment_operations").fetchone()
            == before
        )
        assert journal.renew_claim(db, operation.operation_id, token, lease_seconds=1)
        assert (
            db.execute("SELECT lease_token,lease_until FROM payment_operations").fetchone()
            == before
        )
    clock.advance(offset)
    with other.transaction() as db:
        assert not other.renew_claim(db, operation.operation_id, token)
        successor = other.claim(db, operation.operation_id)
        assert successor != token
        assert not other.renew_claim(db, operation.operation_id, token)
        other.release_claim(db, operation.operation_id, token)
        assert other.owns(db, operation.operation_id, successor)
        other.invalidate_operation(db, operation.operation_id)
        assert not other.renew_claim(db, operation.operation_id, successor)
        assert other.claim(db, operation.operation_id) is None


@pytest.mark.parametrize("failure", ["reject", "database", "cancel", "budget"])
def test_stops_preserve_nonce_and_restart_identity(rig, monkeypatch, failure):
    clock, journal, _, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)
    rpc.delay = 4
    if failure in ("reject", "database"):

        def renew(*args, **kwargs):
            if failure == "database":
                raise sqlite3.OperationalError("synthetic contention")
            return False

        monkeypatch.setattr(journal, "renew_claim", renew)
    elif failure == "cancel":
        rpc.hook = lambda *args: worker.stop() if clock.elapsed >= 32 else None
    else:
        worker.attempt_factory = lambda *args, **kwargs: clock.attempt(80, **kwargs)
    result = worker.run_one(operation.operation_id, broadcast=True)
    assert result.state == "reserved" and result.nonce == 0
    assert result.error.startswith("attempt stopped:")
    assert_unsubmitted(rig, operation)
    assert current_attempt() is None
    monkeypatch.undo()
    rpc.delay, rpc.hook = 0, None
    restarted = lab.laboratory_executor(PaymentJournal(journal.path), rig[4])
    result = restarted.run_one(operation.operation_id, broadcast=True)
    assert result.state == "submitted" and result.nonce == 0
    assert result.operation_id == operation.operation_id and len(rpc.broadcasts) == 1


def test_late_rpc_result_cannot_save_send_or_release_successor(rig):
    clock, journal, _, rpc, _ = rig
    operation = reserve(rig)
    entered, release = Event(), Event()
    worker = executor(rig)

    def pause(method, params):
        if method == "eth_estimateGas":
            entered.set()
            assert release.wait(3)

    rpc.hook = pause
    other = PaymentJournal(journal.path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker.run_one, operation.operation_id, broadcast=True)
        try:
            assert entered.wait(3)
            clock.advance(120)
            with other.transaction() as db:
                successor = other.claim(db, operation.operation_id)
                assert successor
        finally:
            release.set()
        assert future.result(timeout=3).state == "reserved"
    assert assert_unsubmitted(rig, operation).nonce == 0
    with other.transaction() as db:
        assert other.owns(db, operation.operation_id, successor)


def test_two_workers_and_signer_nonce_serialization(rig):
    _, journal, payment, rpc, transport = rig
    first = reserve(rig)
    second_payment = lab.create_fixture(
        transport.config, "other", payment.terms.payment_info.payer, 1000, 3600, offline=True
    )
    second = lab.operation_for(second_payment, "fund")
    with journal.transaction() as db:
        journal.create_payment(db, second_payment)
        journal.reserve(db, second, "0x" + buyer_signature(second_payment.terms).hex())
    entered, release = Event(), Event()

    def pause(method, params):
        if method == "eth_estimateGas":
            entered.set()
            assert release.wait(3)

    rpc.hook = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(executor(rig).run_one, first.operation_id, broadcast=True)
        try:
            assert entered.wait(3)
            competitor = lab.laboratory_executor(PaymentJournal(journal.path), transport)
            assert competitor.run_one(first.operation_id, broadcast=True).state == "reserved"
            assert competitor.run_one(second.operation_id, broadcast=True).nonce is None
        finally:
            release.set()
        assert future.result(timeout=3).state == "submitted"
    assert len(rpc.broadcasts) == 1


@pytest.mark.parametrize("action", ["fund", "capture"])
@pytest.mark.parametrize("boundary", ["sign", "send"])
def test_financial_deadline_reached_inside_transport(rig, action, boundary):
    clock, journal, payment, rpc, transport = rig
    worker = executor(rig)
    if action == "capture":
        funding = reserve(rig)
        worker.run_one(funding.operation_id, broadcast=True)
        assert worker.run_one(funding.operation_id).state == "confirmed"
        rpc.broadcasts.clear()
    operation = reserve(rig, action)
    before = payment.terms
    deadline = (
        before.payment_info.pre_approval_expiry
        if action == "fund"
        else before.payment_info.authorization_expiry
    )
    clock.chain = deadline - 100

    def expire(method, params):
        trigger = method == "eth_getBalance" and params[1] == "pending"
        if boundary == "send":
            with journal.transaction() as db:
                trigger = journal.get(db, operation.operation_id).state == "submitted"
        if trigger:
            clock.advance(100)

    rpc.hook = expire
    result = worker.run_one(operation.operation_id, broadcast=True)
    assert result.state == ("invalidated" if boundary == "sign" else "submitted")
    assert not rpc.broadcasts
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).terms == before
        assert not any(
            op.intent.action == "void" for op in journal.operations(db, payment.payment_id)
        )


def test_domain_invalidation_before_signing(rig):
    _, journal, _, rpc, _ = rig
    operation = reserve(rig)

    def invalidate(method, params):
        if method == "eth_estimateGas":
            with journal.transaction() as db:
                journal.invalidate_operation(db, operation.operation_id)

    rpc.hook = invalidate
    result = executor(rig).run_one(operation.operation_id, broadcast=True)
    assert result.state == "invalidated"
    assert_unsubmitted(rig, operation, state="invalidated")


@pytest.mark.parametrize("budget", [180, 80])
def test_slow_receipt_inspection_after_financial_expiry(rig, budget):
    clock, journal, payment, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)
    submitted = worker.run_one(operation.operation_id, broadcast=True)
    clock.advance(4000)
    rpc.delay = 10
    worker.attempt_factory = lambda *args, **kwargs: clock.attempt(budget, **kwargs)
    result = worker.run_one(operation.operation_id)
    assert result.state == ("confirmed" if budget == 180 else "submitted")
    assert result.nonce == submitted.nonce and result.transaction_hash == submitted.transaction_hash
    assert len(rpc.broadcasts) == 1
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).terms == payment.terms
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == (budget == 180)
    rpc.delay = 0
    assert executor(rig).run_one(operation.operation_id).state == "confirmed"
    assert executor(rig).run_one(operation.operation_id).state == "confirmed"
    assert len(rpc.broadcasts) == 1


def test_slow_reclaim_shares_budget_and_payer_ownership(rig):
    clock, journal, payment, rpc, transport = rig
    operation = reserve(rig)
    worker = executor(rig)
    worker.run_one(operation.operation_id, broadcast=True)
    assert worker.run_one(operation.operation_id).state == "confirmed"
    clock.advance(3600)
    reclaim = reserve(rig, "reclaim")
    rpc.delay = 4
    with clock.attempt().scope() as attempt:
        stage_reclaim(journal, transport, reclaim.operation_id, BUYER_KEY)
        result = lab.laboratory_executor(
            journal, ReclaimSubmission(transport, payment.terms)
        ).run_one(reclaim.operation_id, broadcast=True, attempt=attempt)
    assert result.state == "submitted" and result.nonce == 0
    assert 120 < clock.elapsed - 3600 < 300
    with journal.transaction() as db:
        assert (
            journal.private(db, reclaim.operation_id)[2].lower()
            == payment.terms.payment_info.payer.lower()
        )
    rpc.delay = 0
    assert worker.run_one(reclaim.operation_id).state == "confirmed"
    assert len(rpc.broadcasts) == 2


def test_process_interruption_clears_scope_and_retains_nonce(rig):
    _, journal, _, rpc, _ = rig
    operation = reserve(rig)

    class Interruption(BaseException):
        pass

    def interrupt(method, params):
        if method == "eth_estimateGas":
            raise Interruption

    rpc.hook = interrupt
    with pytest.raises(Interruption):
        executor(rig).run_one(operation.operation_id, broadcast=True)
    assert current_attempt() is None
    assert assert_unsubmitted(rig, operation).nonce == 0
    with journal.transaction() as db:
        assert db.execute("SELECT lease_token FROM payment_operations").fetchone() == (None,)


def test_no_rpc_started_without_its_full_timeout_budget(rig):
    clock, _, _, rpc, transport = rig
    with clock.attempt(15).scope():
        with pytest.raises(AttemptStopped, match="budget"):
            transport.pending_nonce(transport.config.operator_address)
    assert rpc.calls == []


def test_shutdown_signals_active_rpc_then_drains_without_late_effects(rig):
    _, _, _, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)
    entered, release = Event(), Event()

    def pause(method, params):
        if method == "eth_estimateGas":
            entered.set()
            assert release.wait(3)

    rpc.hook = pause

    async def lifespan():
        async with background_workers(
            (("payments", lambda: worker.run_one(operation.operation_id, broadcast=True), 1),),
            on_stop=worker.stop,
        ):
            assert await asyncio.to_thread(entered.wait, 3)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, lifespan())
        try:
            assert worker.cancelled.wait(3)
            assert not future.done()  # No claim that Python can kill the synchronous call.
        finally:
            release.set()
        future.result(timeout=3)
    assert assert_unsubmitted(rig, operation).nonce == 0
    assert worker.run_one(operation.operation_id, broadcast=True) is None


def test_cancel_after_submitted_before_send_remains_unresolved(rig):
    _, journal, _, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)

    def cancel(method, params):
        with journal.transaction() as db:
            if journal.get(db, operation.operation_id).state == "submitted":
                worker.stop()

    rpc.hook = cancel
    result = worker.run_one(operation.operation_id, broadcast=True)
    assert result.state == "submitted" and "cancelled" in result.error
    with journal.transaction() as db:
        private = journal.private(db, operation.operation_id)
        assert private[0] is not None
    rpc.hook = None
    for _ in range(2):
        later = executor(rig).run_one(operation.operation_id, broadcast=True)
        assert later.state == "submitted" and later.nonce == result.nonce
        assert later.transaction_hash == result.transaction_hash
    assert not rpc.broadcasts
    with journal.transaction() as db:
        assert journal.private(db, operation.operation_id) == private
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0


def test_stale_receipt_cannot_commit_over_successor(rig):
    clock, journal, _, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)
    worker.run_one(operation.operation_id, broadcast=True)
    other = PaymentJournal(journal.path)
    successor = []

    def takeover(method, params):
        if method == "eth_getTransactionReceipt":
            clock.lease += 120
            with other.transaction() as db:
                successor.append(other.claim(db, operation.operation_id))

    rpc.hook = takeover
    stale = worker.run_one(operation.operation_id)
    assert stale.state == "submitted" and successor[0]
    with other.transaction() as db:
        assert other.owns(db, operation.operation_id, successor[0])
        assert db.execute("SELECT count(*) FROM payment_observations").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
        other.release_claim(db, operation.operation_id, successor[0])
    rpc.hook = None
    assert worker.run_one(operation.operation_id).state == "confirmed"
    assert len(rpc.broadcasts) == 1


def test_late_send_error_cannot_overwrite_successor_and_never_resends(rig):
    clock, journal, _, rpc, _ = rig
    operation = reserve(rig)
    other = PaymentJournal(journal.path)
    request = rpc.request
    successor = []

    def response_loss(method, params):
        result = request(method, params)
        if method == "eth_sendRawTransaction":
            clock.lease += 120
            with other.transaction() as db:
                successor.append(other.claim(db, operation.operation_id))
            raise TimeoutError("private injected RPC detail")
        return result

    rpc.request = response_loss
    result = executor(rig).run_one(operation.operation_id, broadcast=True)
    assert result.state == "submitted" and result.error is None
    assert len(rpc.broadcasts) == 1
    with other.transaction() as db:
        assert other.owns(db, operation.operation_id, successor[0])
        other.release_claim(db, operation.operation_id, successor[0])
    rpc.request = request
    confirmed = executor(rig).run_one(operation.operation_id)
    assert confirmed.state == "confirmed" and confirmed.transaction_hash == result.transaction_hash
    assert confirmed.nonce == result.nonce and len(rpc.broadcasts) == 1


def test_reclaim_budget_keeps_payer_nonce_for_later_attempt(rig):
    clock, journal, _, rpc, transport = rig
    funding = reserve(rig)
    worker = executor(rig)
    worker.run_one(funding.operation_id, broadcast=True)
    worker.run_one(funding.operation_id)
    clock.advance(3600)
    reclaim = reserve(rig, "reclaim")
    rpc.delay = 4
    with clock.attempt(180).scope(), pytest.raises(AttemptStopped, match="budget"):
        stage_reclaim(journal, transport, reclaim.operation_id, BUYER_KEY)
    with journal.transaction() as db:
        current = journal.get(db, reclaim.operation_id)
        assert current.state == "reserved" and current.nonce == 0
        assert journal.private(db, reclaim.operation_id)[0] is None
    rpc.delay = 0
    with clock.attempt().scope():
        stage_reclaim(journal, transport, reclaim.operation_id, BUYER_KEY)
    with journal.transaction() as db:
        current = journal.get(db, reclaim.operation_id)
        assert current.state == "signed" and current.nonce == 0
    assert len(rpc.broadcasts) == 1


def test_confirmation_callback_cannot_commit_after_lease_expires(rig):
    clock, journal, payment, rpc, _ = rig
    operation = reserve(rig)
    worker = executor(rig)
    worker.run_one(operation.operation_id, broadcast=True)
    complete = worker.complete

    def slow_booking(db, operation, evidence):
        complete(db, operation, evidence)
        clock.lease += 120

    worker.complete = slow_booking
    result = worker.run_one(operation.operation_id)
    assert result.state == "submitted"
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).state == "funding_pending"
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM payment_observations").fetchone()[0] == 0
    assert executor(rig).run_one(operation.operation_id).state == "confirmed"
    assert len(rpc.broadcasts) == 1
