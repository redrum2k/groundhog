"""Cooperative synchronous attempts. No background task can outlive this scope.

Checkpoints surround every Base RPC (15s maximum), and precede signing/send and
durable writes. Renew every 30 elapsed seconds: 30 + 15 RPC + 10 SQLite contention
leaves 65 seconds of the 120s lease. A delayed/blocked call cannot revive ownership.
No RPC, signer, wait or join runs under the short renewal transaction.
"""

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event

from app.orders.service import DomainError

RPC_SECONDS = 15
SUBMISSION_SECONDS = 300
INSPECTION_SECONDS = 180
RENEW_SECONDS = 30
logger = logging.getLogger(__name__)
_current = ContextVar("payment_attempt", default=None)


class AttemptStopped(ValueError):
    pass


class ActionIneligible(AttemptStopped):
    pass


def current_attempt():
    return _current.get()


def checkpoint(*, reserve=0, effect=False):
    attempt = current_attempt()
    if attempt is not None:
        attempt.checkpoint(reserve=reserve, effect=effect)


class PaymentAttempt:
    def __init__(self, seconds=SUBMISSION_SECONDS, *, clock=None, cancelled=None):
        if not 0 < seconds <= SUBMISSION_SECONDS:
            raise ValueError("payment attempt budget must be finite and at most 300 seconds")
        self.clock = clock or time.monotonic
        self.started_at = self.clock()
        self.end = self.started_at + seconds
        self.cancelled = cancelled if cancelled is not None else Event()
        self.stopped = None
        self.sent = False
        self.executor_cancelled = None
        self.binding = None
        self.action = self.terms = None
        self.inspection = False
        self.chain_anchor = None
        self.remaining_authority = None

    @contextmanager
    def scope(self):
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def configure(self, action, terms, *, inspection=False, remaining_authority=None):
        self.action, self.terms, self.inspection = action, terms, inspection
        self.remaining_authority = remaining_authority
        if inspection:
            self.end = min(self.end, self.started_at + INSPECTION_SECONDS)

    @contextmanager
    def claim(self, journal, operation_id, token, guard=None):
        if self.binding is not None:
            raise RuntimeError("attempt already owns a claim")
        self.binding = (journal, operation_id, token, guard)
        self.renewed_at = self.clock()
        try:
            yield self
        finally:
            self.binding = None
            # Token comparison protects successors, even after cancellation/expiry.
            try:
                with journal.transaction() as db:
                    journal.release_claim(db, operation_id, token)
            except Exception:
                logger.warning("payment claim cleanup unavailable operation=%s", operation_id)

    def stop(self, reason, *, ineligible=False):
        self.stopped = ActionIneligible(reason) if ineligible else AttemptStopped(reason)
        raise self.stopped

    def check_time(self, reserve=0):
        if self.stopped is not None:
            raise self.stopped
        if self.cancelled.is_set() or (
            self.executor_cancelled is not None and self.executor_cancelled.is_set()
        ):
            self.stop("cancelled")
        if self.clock() + reserve >= self.end:
            self.stop("elapsed attempt budget exhausted")
        if self.inspection:
            return
        if self.remaining_authority is not None and self.remaining_authority() <= reserve:
            self.stop("accepted financial deadline or submission cutoff reached", ineligible=True)
        if self.terms is not None and self.chain_anchor is not None:
            timestamp, observed_at = self.chain_anchor
            now = timestamp + max(0, self.clock() - observed_at)
            info = self.terms.payment_info
            cutoff = {"fund": info.pre_approval_expiry, "capture": info.authorization_expiry}.get(
                self.action
            )
            if cutoff is not None and now + reserve >= cutoff:
                self.stop("accepted chain deadline reached", ineligible=True)

    def observe_chain(self, timestamp, started_at):
        # Anchor at request START: includes the full read latency conservatively.
        # Never move the estimated chain time backward on repeated/stale heads.
        if self.chain_anchor is not None:
            old, observed_at = self.chain_anchor
            timestamp = max(timestamp, old + max(0, started_at - observed_at))
        self.chain_anchor = (timestamp, started_at)

    def check_db(self, db, *, effect=False):
        self.check_time()
        journal, operation_id, token, guard = self.binding
        operation = journal.get(db, operation_id)
        if not journal.owns(db, operation_id, token):
            self.stop("claim ownership lost")
        allowed = (
            ("submitted", "uncertain", "confirmed")
            if self.inspection
            else ("reserved", "signed", "submitted")
        )
        if operation.state not in allowed:
            self.stop("operation no longer eligible", ineligible=True)
        if effect and not self.inspection and operation.state in ("reserved", "signed"):
            try:
                if guard is not None and guard(db, operation) is False:
                    self.stop("current settlement eligibility changed", ineligible=True)
            except DomainError:
                self.stop("current settlement eligibility changed", ineligible=True)
        self.check_time()
        if not journal.owns(db, operation_id, token):
            self.stop("claim ownership lost")
        return operation

    def checkpoint(self, *, reserve=0, effect=False):
        self.check_time(reserve)
        if self.binding is not None:
            journal, operation_id, token, _ = self.binding
            try:
                with journal.transaction() as db:
                    operation = self.check_db(db, effect=effect)
                    if self.clock() - self.renewed_at >= RENEW_SECONDS:
                        activity = (
                            "inspect"
                            if self.inspection
                            else ("submit" if operation.state == "submitted" else "prepare")
                        )
                        if not journal.renew_claim(db, operation_id, token, activity=activity):
                            self.stop("claim renewal rejected")
                        self.renewed_at = self.clock()
                        logger.debug("payment claim renewed operation=%s", operation_id)
            except AttemptStopped:
                raise
            except Exception:
                self.stop("claim checkpoint unavailable")
        self.check_time(reserve)
