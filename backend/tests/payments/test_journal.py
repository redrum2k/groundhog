from datetime import UTC, datetime

import pytest

from app.contracts.models import Money
from app.contracts.payments import (
    CatalogPaymentIntent,
    PaymentAccount,
    PaymentBinding,
    PaymentInfo,
    PaymentOperation,
    PaymentTerms,
)
from app.orders.service import DomainError
from app.payments.executor import ChainObservation, FakeChainTransport, PaymentExecutor
from app.payments.journal import PaymentJournal

NOW = datetime(2026, 10, 23, tzinfo=UTC)
TOKEN = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"


def account(identifier="p1", mode="base_sepolia"):
    info = PaymentInfo(
        operator="0x" + "1" * 40,
        payer="0x" + "2" * 40,
        receiver="0x" + "3" * 40,
        token=TOKEN,
        max_amount=100000,
        pre_approval_expiry=2000000000,
        authorization_expiry=2000000100,
        refund_expiry=2000000200,
        fee_receiver="0x" + "0" * 40,
        salt=1,
    )
    terms = PaymentTerms(
        payment_id=identifier,
        mode=mode,
        asset_address=TOKEN,
        amount_atomic=100000,
        payment_info=info,
        escrow_address="0x" + "4" * 40,
        collector_address="0x" + "5" * 40,
        payment_hash="0x" + ("6" if identifier == "p1" else "7") * 64,
        authorization_nonce="0x" + "8" * 64,
        pricing_rule="isolated-test-usdc-0.10-v1",
        display_amount=Money(amount_minor=10, currency="USD", decimals=2),
        settlement_terms="Explicit test-only 1 USD : 1 USDC conversion",
    )
    return PaymentAccount(
        payment_id=identifier,
        order_id="order-" + identifier,
        snapshot_id="snapshot-" + identifier,
        terms=terms,
        state="awaiting_signature",
        created_at=NOW,
        updated_at=NOW,
    )


def operation(payment, action="fund", key="key", revision=1):
    identifier = payment.payment_id + ":" + key
    intent = CatalogPaymentIntent(
        operation_id=identifier,
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        snapshot_id=payment.snapshot_id,
        binding=PaymentBinding(
            snapshot_id=payment.snapshot_id, evidence_revision=revision, delivery_version=0
        ),
        action=action,
        amount_atomic=payment.terms.amount_atomic,
        payment_hash=payment.terms.payment_hash,
        idempotency_key=key,
        reason="synthetic accepted fixture decision",
        mode=payment.terms.mode,
    )
    return PaymentOperation(
        operation_id=identifier,
        intent=intent,
        fingerprint="sha256-fixture",
        created_at=NOW,
        updated_at=NOW,
    )


def reserve(journal, payment, action="fund", key="key", **kwargs):
    op = operation(payment, action, key, **kwargs)
    with journal.transaction() as db:
        journal.create_payment(db, payment)
        journal.reserve(db, op, private_authorization="private-buyer-capability")
    return op


def observed(op, payment, confirmations=2, canonical=True):
    action = op.intent.action
    return ChainObservation(
        "confirmed",
        block_number=100,
        block_hash="0x" + "a" * 64,
        confirmations=confirmations,
        canonical=canonical,
        event={
            "name": {
                "fund": "PaymentAuthorized",
                "capture": "PaymentCaptured",
                "void": "PaymentVoided",
                "reclaim": "PaymentReclaimed",
            }[action],
            "payment_hash": payment.terms.payment_hash,
            "amount_atomic": payment.terms.amount_atomic,
        },
        payment_state={
            "payment_hash": payment.terms.payment_hash,
            "has_collected_payment": True,
            "capturable_amount": payment.terms.amount_atomic if action == "fund" else 0,
            "refundable_amount": payment.terms.amount_atomic if action == "capture" else 0,
            "block_number": 100,
            "block_hash": "0x" + "a" * 64,
        },
    )


def update_account(journal, calls):
    def complete(db, op, evidence):
        calls.append(op.operation_id)
        payment = journal.payment(db, op.intent.payment_id)
        state = {"fund": "funded", "capture": "captured", "void": "voided"}[op.intent.action]
        journal.save_payment(db, payment.model_copy(update={"state": state}))

    return complete


def test_submit_is_not_funding_and_confirmation_is_atomic_and_unique(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account()
    op = reserve(journal, payment)
    chain = FakeChainTransport()
    calls = []
    executor = PaymentExecutor(journal, chain, complete=update_account(journal, calls))
    assert executor.run_one(op.operation_id).state == "reserved"
    assert not chain.signed
    submitted = executor.run_one(op.operation_id, broadcast=True)
    assert submitted.state == "submitted"
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).state == "awaiting_signature"
        assert not db.execute("SELECT * FROM payment_effects").fetchall()
        private = journal.private(db, op.operation_id)
        assert private[0] == chain.broadcasts[0]
        assert "private-buyer-capability" not in journal.get(db, op.operation_id).model_dump_json()
    chain.observations[submitted.transaction_hash] = observed(op, payment, confirmations=1)
    assert executor.run_one(op.operation_id).state == "submitted"
    assert not calls
    chain.observations[submitted.transaction_hash] = observed(op, payment)
    assert executor.run_one(op.operation_id).state == "confirmed"
    assert executor.run_one(op.operation_id).state == "confirmed"
    assert calls == [op.operation_id]
    with journal.transaction() as db:
        assert journal.payment(db, payment.payment_id).state == "funded"
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 1


def test_exact_replay_and_changed_payload_signature_or_terms_rejected(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account(mode="mock")
    op = reserve(journal, payment)
    PaymentExecutor(journal).run_one(op.operation_id)
    with journal.transaction() as db:
        replay = journal.reserve(db, op, "private-buyer-capability")
        assert replay.model_dump_json() == op.model_dump_json()
        assert journal.get(db, op.operation_id).state == "confirmed"
        with pytest.raises(DomainError, match="changed payment request"):
            journal.reserve(db, op, "different-signature")
        changed = op.model_copy(update={"intent": op.intent.model_copy(update={"reason": "new"})})
        with pytest.raises(DomainError, match="changed payment request"):
            journal.reserve(db, changed, "private-buyer-capability")
        bad_terms = payment.terms.model_copy(update={"settlement_terms": "changed terms"})
        with pytest.raises(DomainError, match="immutable"):
            journal.save_payment(db, payment.model_copy(update={"terms": bad_terms}))


def test_capture_and_void_compete_even_after_confirmation(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account(mode="mock")
    capture = reserve(journal, payment, "capture", "capture")
    with journal.transaction() as db:
        with pytest.raises(DomainError, match="active or confirmed"):
            journal.reserve(db, operation(payment, "void", "void"))
        journal.complete_mock(db, capture.operation_id)
        with pytest.raises(DomainError, match="active or confirmed"):
            journal.reserve(db, operation(payment, "void", "void"))
        assert journal.terminal(db, payment.payment_id).intent.action == "capture"


def test_lost_broadcast_response_and_restart_never_resigns_or_rebroadcasts(tmp_path):
    path = tmp_path / "catalog.sqlite"
    journal = PaymentJournal(path)
    payment = account()
    op = reserve(journal, payment)
    chain = FakeChainTransport(nonce=12)
    chain.broadcast_error = TimeoutError("possibly submitted")
    uncertain = PaymentExecutor(journal, chain).run_one(op.operation_id, broadcast=True)
    assert uncertain.state == "uncertain"
    restarted = PaymentJournal(path)
    executor = PaymentExecutor(restarted, chain)
    missing = executor.run_one(op.operation_id, broadcast=True)
    assert missing.state in ("submitted", "uncertain")
    assert missing.nonce == 12
    assert missing.transaction_hash == uncertain.transaction_hash
    assert len(chain.signed) == len(chain.broadcasts) == 1
    chain.observations[uncertain.transaction_hash] = observed(op, payment)
    assert executor.run_one(op.operation_id).state == "confirmed"
    assert len(chain.signed) == len(chain.broadcasts) == 1


def test_signing_is_outside_lock_and_stale_binding_invalidates_before_broadcast(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account()
    op = reserve(journal, payment, "capture")
    current = {"revision": 1}

    class ChangedDuringSigning(FakeChainTransport):
        def prepare_transaction(self, *args, **kwargs):
            # A concurrent order mutation can commit while transaction preparation runs.
            with journal.transaction() as db:
                assert journal.get(db, op.operation_id).nonce == 0
                current["revision"] = 2
            return super().prepare_transaction(*args, **kwargs)

    chain = ChangedDuringSigning()
    executor = PaymentExecutor(
        journal,
        chain,
        guard=lambda db, item: item.intent.binding.evidence_revision == current["revision"],
    )
    assert executor.run_one(op.operation_id, broadcast=True).state == "invalidated"
    assert not chain.broadcasts
    replacement = reserve(journal, payment, "void", "replacement", revision=2)
    normal_chain = FakeChainTransport()
    assert (
        PaymentExecutor(journal, normal_chain)
        .run_one(replacement.operation_id, broadcast=True)
        .nonce
        == 0
    )


def test_operator_nonces_are_serialized_across_payments(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    first, second = account(), account("p2")
    a, b = reserve(journal, first), reserve(journal, second)
    chain = FakeChainTransport(nonce=3)
    executor = PaymentExecutor(journal, chain)
    submitted = executor.run_one(a.operation_id, broadcast=True)
    assert executor.run_one(b.operation_id, broadcast=True).state == "reserved"
    assert len(chain.signed) == 1
    chain.observations[submitted.transaction_hash] = observed(a, first)
    executor.run_one(a.operation_id)
    assert executor.run_one(b.operation_id, broadcast=True).nonce == 4


def test_persist_signed_bytes_before_broadcast_and_submission_survives_new_dispute(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account()
    op = reserve(journal, payment, "capture")
    eligible = {"value": True}

    class InspectingTransport(FakeChainTransport):
        def broadcast(self, raw_transaction, explicit_testnet_broadcast=False):
            with journal.transaction() as db:
                stored = journal.get(db, op.operation_id)
                assert stored.state == "submitted"
                assert journal.private(db, op.operation_id)[0] == raw_transaction
                assert stored.transaction_hash == self.signed[-1].transaction_hash
            eligible["value"] = False
            return super().broadcast(raw_transaction, explicit_testnet_broadcast)

    chain = InspectingTransport()
    executor = PaymentExecutor(journal, chain, guard=lambda db, item: eligible["value"])
    submitted = executor.run_one(op.operation_id, broadcast=True)
    with journal.transaction() as db:
        assert not journal.invalidate(db, payment.payment_id)
    chain.observations[submitted.transaction_hash] = observed(op, payment)
    assert executor.run_one(op.operation_id).state == "confirmed"


def test_reorg_holds_existing_booking_and_never_redispatches(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account()
    op = reserve(journal, payment, "capture")
    chain = FakeChainTransport()
    changed = []
    calls = []
    executor = PaymentExecutor(
        journal,
        chain,
        complete=update_account(journal, calls),
        changed=lambda db, item, evidence: changed.append(item.state),
    )
    submitted = executor.run_one(op.operation_id, broadcast=True)
    chain.observations[submitted.transaction_hash] = observed(op, payment)
    executor.run_one(op.operation_id)
    chain.observations[submitted.transaction_hash] = observed(op, payment, canonical=False)
    assert executor.run_one(op.operation_id).state == "orphaned"
    assert changed[-1] == "orphaned"
    assert executor.run_one(op.operation_id, broadcast=True).state == "orphaned"
    assert calls == [op.operation_id]
    assert len(chain.broadcasts) == 1
    with journal.transaction() as db:
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 1


def test_callback_failure_rolls_back_confirmation_and_booking_together(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account(mode="mock")
    op = reserve(journal, payment, "capture")

    def broken(db, operation, evidence):
        raise RuntimeError("catalog completion failed")

    with pytest.raises(RuntimeError, match="catalog completion"):
        PaymentExecutor(journal, complete=broken).run_one(op.operation_id)
    with journal.transaction() as db:
        assert journal.get(db, op.operation_id).state == "reserved"
        assert not db.execute("SELECT * FROM payment_effects").fetchall()
    assert PaymentExecutor(journal).run_one(op.operation_id).state == "confirmed"


def test_rejected_transaction_never_books_an_effect(tmp_path):
    journal = PaymentJournal(tmp_path / "catalog.sqlite")
    payment = account()
    op = reserve(journal, payment, "capture")
    chain = FakeChainTransport()
    executor = PaymentExecutor(journal, chain)
    submitted = executor.run_one(op.operation_id, broadcast=True)
    chain.observations[submitted.transaction_hash] = ChainObservation(
        "failed",
        block_number=100,
        block_hash="0x" + "a" * 64,
        confirmations=2,
        canonical=True,
        error="transaction reverted",
    )
    assert executor.run_one(op.operation_id).state == "failed"
    with journal.transaction() as db:
        assert not db.execute("SELECT * FROM payment_effects").fetchall()
