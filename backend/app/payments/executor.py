"""Bounded outbox execution. Transport calls and signing always occur outside SQLite locks.

A submitted transaction is reconciled, never automatically replaced or rebroadcast. A
restart after marking submitted but before broadcast deliberately requires recovery.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from threading import Event
from typing import Literal, Protocol

from app.contracts.payments import BlockEvidence, EscrowObservation
from app.payments.attempt import (
    SUBMISSION_SECONDS,
    ActionIneligible,
    AttemptStopped,
    PaymentAttempt,
    checkpoint,
    current_attempt,
)
from app.payments.base_rpc import BaseTransportError
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
        authority=None,
        attempt_factory=PaymentAttempt,
    ):
        self.journal = journal
        self.transport = transport
        self.guard = guard
        self.complete = complete
        self.changed = changed
        self.authority = authority
        self.attempt_factory = attempt_factory
        self.cancelled = Event()

    def stop(self):
        """Stop future work and signal active synchronous attempts; callers drain them."""
        self.cancelled.set()

    def _changed(self, db, operation, evidence=None):
        if self.changed is not None:
            self.changed(db, operation, evidence or {})
        return operation

    def run_one(self, operation_id=None, *, broadcast=False, attempt=None):
        """Process one operation or audit the latest confirmed receipt.

        Live signing/submission requires explicit broadcast=True; inspection and receipt
        reconciliation remain available by default. Transport adds its own opt-in guard.
        """
        if self.cancelled.is_set():
            return None
        attempt = attempt or self.attempt_factory(SUBMISSION_SECONDS, cancelled=self.cancelled)
        attempt.executor_cancelled = self.cancelled
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
            terms = self.journal.payment_terms(db, operation.intent.payment_id)
            inspection = operation.state in ("submitted", "uncertain", "confirmed")
            remaining = self.authority(db, operation) if self.authority and not inspection else None
        attempt.configure(
            operation.intent.action, terms, inspection=inspection, remaining_authority=remaining
        )
        with attempt.scope(), attempt.claim(self.journal, operation_id, token, self.guard):
            try:
                checkpoint(effect=True)
                return self._process(operation_id, token, broadcast)
            except AttemptStopped as error:
                return self._stopped(operation_id, token, error)
            except sqlite3.Error:
                return self._stopped(operation_id, token, AttemptStopped("journal unavailable"))

    def _stopped(self, operation_id, token, error):
        current_attempt().stopped = error
        logging.getLogger(__name__).warning(
            "payment attempt stopped operation=%s reason=%s", operation_id, error
        )
        with self.journal.transaction() as db:
            operation = self.journal.get(db, operation_id)
            if not self.journal.owns(db, operation_id, token):
                return operation
            if isinstance(error, ActionIneligible) and operation.state in ("reserved", "signed"):
                return self._changed(
                    db, self.journal.invalidate_operation(db, operation_id, str(error))
                )
            # Transient stop preserves reservation, nonce and bytes. Submitted remains
            # unresolved, never rolled back or retried. Inspection exhaustion proves nothing.
            return self.journal.update(db, operation_id, error=f"attempt stopped: {error}")

    def _process(self, operation_id, token, broadcast):
        with self.journal.transaction() as db:
            current_attempt().check_db(db, effect=True)
            operation = self.journal.get(db, operation_id)
            terms = self.journal.payment_terms(db, operation.intent.payment_id)
            if operation.intent.mode == "mock":
                if operation.state == "confirmed":
                    return operation
                return self.journal.complete_mock(db, operation_id, self.complete)
        if self.transport is None or (
            not broadcast and operation.state not in ("submitted", "uncertain", "confirmed")
        ):
            # Bounded workers select by last attempt time. A disabled reservation
            # must yield its turn so other submitted payments can still reconcile.
            with self.journal.transaction() as db:
                current_attempt().check_db(db)
                if self.journal.owns(db, operation_id, token):
                    return self.journal.update(db, operation_id)
                return self.journal.get(db, operation_id)
        if operation.state in ("submitted", "uncertain", "confirmed"):
            return self._reconcile(operation, terms, token)
        if operation.state == "reserved":
            try:
                checkpoint(effect=True)
                nonce = self.transport.pending_nonce(terms.payment_info.operator)
                with self.journal.transaction() as db:
                    current_attempt().check_db(db, effect=True)
                    operation = self.journal.get(db, operation_id)
                    if not self.journal.owns(db, operation_id, token):
                        return operation
                    if operation.state != "reserved":
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
                    current_attempt().check_db(db, effect=True)
                    if not self.journal.owns(db, operation_id, token):
                        return self.journal.get(db, operation_id)
                    operation = self.journal.get(db, operation_id)
                    if operation.state != "reserved":
                        return self.journal.get(db, operation_id)
                    operation = self.journal.save_signed(db, operation_id, signed)
            except AttemptStopped:
                raise
            except Exception as error:
                return self._before_submission_failure(operation_id, token, error)
        with self.journal.transaction() as db:
            current_attempt().check_db(db, effect=True)
            operation = self.journal.get(db, operation_id)
            if not self.journal.owns(db, operation_id, token):
                return operation
            if operation.state != "signed":
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
            checkpoint(effect=True)
            returned_hash = self.transport.broadcast(
                raw_transaction, explicit_testnet_broadcast=True
            )
            if returned_hash.lower() != operation.transaction_hash.lower():
                raise ValueError("RPC returned another transaction hash")
            checkpoint()
            current_attempt().sent = True
        except AttemptStopped:
            raise
        except Exception as error:
            with self.journal.transaction() as db:
                current_attempt().check_db(db)
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
        if isinstance(error, sqlite3.Error):
            current_attempt().stop("journal unavailable")
        checkpoint()
        with self.journal.transaction() as db:
            current_attempt().check_db(db)
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
                error=(
                    f"BaseTransportError: transaction preparation failed before submission: {error}"
                    if type(error) is BaseTransportError
                    else f"{type(error).__name__}: transaction preparation failed before submission"
                ),
            )
            return self._changed(db, operation)

    def _reconcile(self, operation, terms, token):
        try:
            observation = self.transport.reconcile(
                operation.intent.action, terms, operation.transaction_hash
            )
            evidence = asdict(observation)
        except AttemptStopped:
            raise
        except Exception as error:
            observation = ChainObservation(
                "uncertain", error=f"{type(error).__name__}: receipt inspection unavailable"
            )
            evidence = asdict(observation)
        with self.journal.transaction() as db:
            current_attempt().check_db(db)
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
                    if (
                        block.event
                        != {
                            "fund": "PaymentAuthorized",
                            "capture": "PaymentCaptured",
                            "void": "PaymentVoided",
                            "reclaim": "PaymentReclaimed",
                        }[current.intent.action]
                        or block.payment_hash.lower() != terms.payment_hash.lower()
                        or block.amount_atomic != terms.amount_atomic
                        or payment_state.block_number != block.block_number
                        or payment_state.block_hash.lower() != block.block_hash.lower()
                    ):
                        raise ValueError("event/state does not match operation and receipt block")
                    evidence = {
                        "block_evidence": block.model_dump(mode="json"),
                        "observation": payment_state.model_dump(mode="json"),
                    }
                except (ValueError, TypeError, AttributeError):
                    observation = ChainObservation(
                        "uncertain",
                        error="receipt/event/payment-state evidence does not match intent",
                    )
                else:
                    # Callback failure must escape the transaction and roll back both the
                    # catalog booking and confirmed journal effect, regardless of error type.
                    confirmed = self.journal.confirm(
                        db, current.operation_id, evidence, self.complete
                    )
                    confirmed = self._changed(db, confirmed, evidence)
                    # The booking callback shares this transaction. If it consumed
                    # the remaining lease/budget, roll back BOTH evidence and books.
                    current_attempt().check_db(db)
                    return confirmed
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
