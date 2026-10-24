"""Bounded outbox execution. Transport calls and signing always occur outside SQLite locks.

A submitted transaction is reconciled, never automatically replaced or rebroadcast. A
restart after marking submitted but before broadcast deliberately requires recovery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol

from app.contracts.payments import BlockEvidence, EscrowObservation
from app.orders.service import DomainError
from app.payments.journal import PaymentJournal


@dataclass(frozen=True)
class SignedTransaction:
    raw_transaction: bytes = field(repr=False)
    transaction_hash: str
    sender: str
    nonce: int


@dataclass(frozen=True)
class ChainObservation:
    status: Literal["pending", "confirmed", "failed", "uncertain", "orphaned"]
    block_number: int | None = None
    block_hash: str | None = None
    confirmations: int = 0
    canonical: bool | None = None
    error: str | None = None
    event: dict | None = None
    payment_state: dict | None = None


class PaymentTransport(Protocol):
    def pending_nonce(self, operator: str) -> int: ...

    def prepare_transaction(self, action, terms, nonce, buyer_signature=None): ...

    def broadcast(self, raw_transaction: bytes, explicit_testnet_broadcast=False) -> str: ...

    def reconcile(self, action, terms, transaction_hash: str): ...


class PaymentExecutor:
    def __init__(
        self,
        journal: PaymentJournal,
        transport: PaymentTransport | None = None,
        *,
        guard=None,
        complete=None,
        changed=None,
    ):
        self.journal = journal
        self.transport = transport
        self.guard = guard
        self.complete = complete
        self.changed = changed

    def _changed(self, db, operation, evidence=None):
        if self.changed is not None:
            self.changed(db, operation, evidence or {})
        return operation

    def _eligible(self, db, operation):
        try:
            if self.guard is not None and self.guard(db, operation) is False:
                raise DomainError(409, "payment eligibility changed")
        except DomainError:
            result = self.journal.invalidate_operation(
                db,
                operation.operation_id,
                "settlement eligibility or binding changed before submission",
            )
            self._changed(db, result)
            return False
        return True

    def run_one(self, operation_id=None, *, broadcast=False):
        """Process one operation or audit the latest confirmed receipt.

        Live signing/submission requires explicit broadcast=True; inspection and receipt
        reconciliation remain available by default. Transport adds its own opt-in guard.
        """
        with self.journal.transaction() as db:
            if operation_id is None:
                candidates = self.journal.pending(db, limit=1, include_confirmed=True)
                if not candidates:
                    return None
                operation_id = candidates[0].operation_id
            operation = self.journal.get(db, operation_id)
            if operation.state in ("failed", "invalidated", "orphaned"):
                return operation
            token = self.journal.claim(db, operation_id)
            if token is None:
                return operation
        try:
            return self._process(operation_id, token, broadcast)
        finally:
            with self.journal.transaction() as db:
                self.journal.release_claim(db, operation_id, token)

    def _process(self, operation_id, token, broadcast):
        with self.journal.transaction() as db:
            operation = self.journal.get(db, operation_id)
            terms = self.journal.payment_terms(db, operation.intent.payment_id)
            if operation.intent.mode == "mock":
                if operation.state == "confirmed":
                    return operation
                if not self._eligible(db, operation):
                    return self.journal.get(db, operation_id)
                return self.journal.complete_mock(db, operation_id, self.complete)
        if self.transport is None:
            return operation
        if operation.state in ("submitted", "uncertain", "confirmed"):
            return self._reconcile(operation, terms, token)
        if not broadcast:
            return operation
        if operation.state == "reserved":
            try:
                nonce = self.transport.pending_nonce(terms.payment_info.operator)
                with self.journal.transaction() as db:
                    operation = self.journal.get(db, operation_id)
                    if not self.journal.owns(db, operation_id, token):
                        return operation
                    if operation.state != "reserved" or not self._eligible(db, operation):
                        return self.journal.get(db, operation_id)
                    nonce = self.journal.reserve_nonce(
                        db, operation_id, terms.payment_info.operator, nonce
                    )
                    if nonce is None:
                        return self.journal.update(db, operation_id)
                    _, signature, _ = self.journal.private(db, operation_id)
                signed = self.transport.prepare_transaction(
                    operation.intent.action, terms, nonce, buyer_signature=signature
                )
                with self.journal.transaction() as db:
                    if not self.journal.owns(db, operation_id, token):
                        return self.journal.get(db, operation_id)
                    operation = self.journal.get(db, operation_id)
                    if operation.state != "reserved" or not self._eligible(db, operation):
                        return self.journal.get(db, operation_id)
                    operation = self.journal.save_signed(db, operation_id, signed)
            except Exception as error:
                return self._before_submission_failure(operation_id, token, error)
        with self.journal.transaction() as db:
            operation = self.journal.get(db, operation_id)
            if not self.journal.owns(db, operation_id, token):
                return operation
            if operation.state != "signed" or not self._eligible(db, operation):
                return self.journal.get(db, operation_id)
            raw_transaction, _, _ = self.journal.private(db, operation_id)
            if raw_transaction is None:
                raise RuntimeError("signed operation has no durable transaction")
            # This durable transition is the point of no return for application input.
            # A crash on either side of broadcast reconciles this exact hash and nonce.
            operation = self.journal.update(
                db, operation_id, state="submitted", reconciliation_status="pending", error=None
            )
            self._changed(db, operation)
        try:
            returned_hash = self.transport.broadcast(
                raw_transaction, explicit_testnet_broadcast=True
            )
            if returned_hash.lower() != operation.transaction_hash.lower():
                raise ValueError("RPC returned another transaction hash")
        except Exception as error:
            with self.journal.transaction() as db:
                operation = self.journal.update(
                    db,
                    operation_id,
                    state="uncertain",
                    reconciliation_status="uncertain",
                    error=f"{type(error).__name__}: broadcast unresolved; reconcile saved hash",
                )
                return self._changed(db, operation)
        # Submission cannot produce a funding or ledger effect. A later receipt check does.
        return operation

    def _before_submission_failure(self, operation_id, token, error):
        with self.journal.transaction() as db:
            operation = self.journal.get(db, operation_id)
            if not self.journal.owns(db, operation_id, token) or operation.state not in (
                "reserved",
                "signed",
            ):
                return operation
            self.journal.release_unused_nonce(db, operation_id)
            operation = self.journal.update(
                db,
                operation_id,
                state="failed",
                reconciliation_status="failed",
                error=f"{type(error).__name__}: transaction preparation failed before submission",
            )
            return self._changed(db, operation)

    def _reconcile(self, operation, terms, token):
        try:
            observation = self.transport.reconcile(
                operation.intent.action, terms, operation.transaction_hash
            )
            evidence = asdict(observation)
        except Exception as error:
            observation = ChainObservation(
                "uncertain", error=f"{type(error).__name__}: receipt inspection unavailable"
            )
            evidence = asdict(observation)
        with self.journal.transaction() as db:
            current = self.journal.get(db, operation.operation_id)
            if not self.journal.owns(db, operation.operation_id, token):
                return current
            previous = current.block_evidence
            previous_block = self.journal.last_block(db, operation.operation_id)
            changed_block = bool(
                previous_block
                and observation.block_hash
                and (
                    observation.block_hash.lower() != previous_block[1]
                    or observation.block_number != previous_block[0]
                )
            )
            if observation.status == "orphaned" or observation.canonical is False or changed_block:
                self.journal.record_observation(db, current.operation_id, evidence)
                current = self.journal.update(
                    db,
                    current.operation_id,
                    state="orphaned",
                    reconciliation_status="orphaned",
                    error="receipt changed or became noncanonical; explicit recovery required",
                )
                return self._changed(db, current, evidence)
            if observation.status == "confirmed" and (
                observation.canonical is True and observation.confirmations >= terms.confirmations
            ):
                try:
                    event = observation.event or {}
                    block = BlockEvidence(
                        transaction_hash=current.transaction_hash,
                        block_number=observation.block_number,
                        block_hash=observation.block_hash,
                        observed_head=observation.block_number + observation.confirmations - 1,
                        confirmations=observation.confirmations,
                        canonical=True,
                        event=event.get("name", event.get("event")),
                        payment_hash=event.get("payment_hash"),
                        amount_atomic=event.get("amount_atomic"),
                    )
                    payment_state = EscrowObservation.model_validate(observation.payment_state)
                    self._check_state(current, terms, payment_state)
                    evidence = {
                        "block_evidence": block.model_dump(mode="json"),
                        "observation": payment_state.model_dump(mode="json"),
                    }
                except (ValueError, TypeError):
                    observation = ChainObservation(
                        "uncertain",
                        error="receipt/event/payment-state evidence does not match intent",
                    )
                else:
                    # Callback failure must escape the transaction and roll back both the
                    # catalog booking and confirmed journal effect, regardless of error type.
                    return self.journal.confirm(db, current.operation_id, evidence, self.complete)
            self.journal.record_observation(db, current.operation_id, evidence)
            failed = (
                observation.status == "failed"
                and observation.canonical is True
                and (observation.confirmations >= terms.confirmations)
            )
            # Never erase a booked effect merely because a node temporarily lost a receipt.
            state = "failed" if failed and previous is None else "uncertain"
            if observation.status in ("pending", "confirmed") and previous is None:
                state = "submitted"
            current = self.journal.update(
                db,
                current.operation_id,
                state=state,
                reconciliation_status="failed"
                if state == "failed"
                else "pending"
                if state == "submitted"
                else "uncertain",
                error=observation.error
                or ("receipt absent or below confirmation threshold; no automatic resubmission"),
            )
            return self._changed(db, current, evidence)

    @staticmethod
    def _check_state(operation, terms, state):
        if state.payment_hash.lower() != terms.payment_hash.lower():
            raise ValueError("state belongs to another payment")
        expected = {
            "fund": (True, terms.amount_atomic, 0),
            "capture": (True, 0, terms.amount_atomic),
            "void": (True, 0, 0),
            "reclaim": (True, 0, 0),
        }[operation.intent.action]
        if (
            state.has_collected_payment,
            state.capturable_amount,
            state.refundable_amount,
        ) != expected:
            raise ValueError("payment state does not establish the full operation")


class FakeChainTransport:
    """Offline chain simulator with explicit receipt observations; never performs network I/O."""

    is_fake = True

    def __init__(self, nonce=0):
        self.nonce = nonce
        self.signed = []
        self.broadcasts = []
        self.observations = {}
        self.broadcast_error = None

    def pending_nonce(self, operator):
        return self.nonce

    def prepare_transaction(self, action, terms, nonce, buyer_signature=None):
        import hashlib

        raw = f"fake:{action}:{terms.payment_hash}:{nonce}".encode()
        signed = SignedTransaction(
            raw, "0x" + hashlib.sha256(raw).hexdigest(), terms.payment_info.operator, nonce
        )
        self.signed.append(signed)
        return signed

    def broadcast(self, raw_transaction, explicit_testnet_broadcast=False):
        if not explicit_testnet_broadcast:
            raise ValueError("explicit simulation submission required")
        self.broadcasts.append(raw_transaction)
        if self.broadcast_error is not None:
            raise self.broadcast_error
        import hashlib

        return "0x" + hashlib.sha256(raw_transaction).hexdigest()

    def reconcile(self, action, terms, transaction_hash):
        return self.observations.get(transaction_hash, ChainObservation("pending"))
