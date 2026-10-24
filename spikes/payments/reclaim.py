"""Isolated payer signing into the EXISTING journal/executor, never server buyer signing.

The current executor stages operator signatures only. This lab helper uses its public
journal primitives to stage a payer signature; the unchanged executor owns submission,
lease/reconciliation transitions, and confirmation. A shared signer-selection hook can
replace this helper later. No SQL schema, journal, or executor implementation is forked.
"""

from app.payments.attempt import PaymentAttempt, checkpoint, current_attempt
from app.payments.base_rpc import BaseTransportError
from app.payments.executor import SignedTransaction
from eth_account import Account
from eth_utils import keccak


class ReclaimSubmission:
    """Route only the already-staged reclaim's broadcast through its payer boundary."""

    def __init__(self, transport, terms):
        self.transport = transport
        self.terms = terms

    def pending_nonce(self, operator):
        raise BaseTransportError("stage the payer nonce before running reclaim")

    def prepare_transaction(self, *args, **kwargs):
        raise BaseTransportError("stage the payer signature before running reclaim")

    def broadcast(self, raw_transaction, explicit_testnet_broadcast=False):
        return self.transport.broadcast_reclaim(
            raw_transaction, self.terms, explicit_testnet_broadcast=explicit_testnet_broadcast
        )

    def reconcile(self, action, terms, transaction_hash):
        return self.transport.reconcile(action, terms, transaction_hash)


def stage_reclaim(journal, transport, operation_id, buyer_key):
    """Claim -> reserve payer nonce -> simulate/sign -> persist -> release claim.

    No broadcast here. If interrupted before saving, the original reserved nonce is
    reused; after saving, no key or new signature is needed. All capabilities remain
    in the same private outbox used by PaymentExecutor. Failed inspection holds the
    reservation for explicit recovery instead of making a fresh attempt.
    """
    attempt = current_attempt() or PaymentAttempt()
    with journal.transaction() as db:
        operation = journal.get(db, operation_id)
        if operation.intent.action != "reclaim" or operation.intent.mode != "base_sepolia":
            raise BaseTransportError("payer staging requires a live-mode reclaim operation")
        if operation.state != "reserved":
            return
        token = journal.claim(db, operation_id)
        if token is None:
            raise BaseTransportError("reclaim is leased; inspect the existing operation")
        terms = journal.payment_terms(db, operation.intent.payment_id)
    attempt.configure("reclaim", terms)

    def guard(db, operation):
        return journal.payment(db, operation.intent.payment_id).state == "funded"

    with attempt.scope(), attempt.claim(journal, operation_id, token, guard):
        checkpoint(effect=True)
        if not transport.config.enable_testnet_broadcast:
            raise BaseTransportError("payer signing requires explicit testnet or offline opt-in")
        try:
            signer = Account.from_key(buyer_key)
        except Exception:
            raise BaseTransportError("reclaim requires SPIKE_BUYER_PRIVATE_KEY") from None
        if signer.address.lower() != terms.payment_info.payer.lower():
            raise BaseTransportError("reclaim signer differs from the accepted payer")
        transport.preflight(terms, action="reclaim")
        pending = transport.pending_nonce(signer.address)
        with journal.transaction() as db:
            attempt.check_db(db, effect=True)
            if not journal.owns(db, operation_id, token):
                raise BaseTransportError("reclaim lease expired before nonce reservation")
            payment = journal.payment(db, operation.intent.payment_id)
            if payment.state != "funded" or journal.get(db, operation_id).state != "reserved":
                raise BaseTransportError("reclaim requires current confirmed funding")
            nonce = journal.reserve_nonce(db, operation_id, signer.address, pending)
            if nonce is None:
                raise BaseTransportError("payer has another unresolved operation; reconcile it")
        request = transport.transaction_request("reclaim", terms, nonce)
        checkpoint(effect=True)
        try:
            raw = bytes(signer.sign_transaction(request).raw_transaction)
        except Exception:
            raise BaseTransportError("isolated payer transaction signing failed") from None
        signed = SignedTransaction(raw, "0x" + keccak(raw).hex(), signer.address, nonce)
        with journal.transaction() as db:
            attempt.check_db(db, effect=True)
            if not journal.owns(db, operation_id, token):
                raise BaseTransportError("reclaim lease expired before signature persistence")
            journal.save_signed(db, operation_id, signed)
