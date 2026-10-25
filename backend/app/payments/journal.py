"""Additive payment outbox sharing the catalog's SQLite transaction boundary.

Private authorizations and signed transactions never enter the public operation model.
The database is private application state and must not be exported as a report.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.contracts.payments import BlockEvidence, PaymentAccount, PaymentOperation
from app.orders.service import DomainError

TERMINAL_ACTIONS = ("capture", "void", "reclaim")
FINISHED_STATES = ("confirmed", "failed", "invalidated", "orphaned")
AUDIT_INTERVAL_SECONDS = 60
ACTIVE_TURNS_PER_AUDIT = 8


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PaymentJournal:
    def __init__(self, repository_or_path):
        self.path = Path(getattr(repository_or_path, "path", repository_or_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            self.initialize(db)

    @staticmethod
    def initialize(db):
        statements = (
            "CREATE TABLE IF NOT EXISTS payment_accounts (payment_id TEXT PRIMARY KEY, "
            "order_id TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, terms TEXT NOT NULL, "
            "data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS payment_operations (operation_id TEXT PRIMARY KEY, "
            "payment_id TEXT NOT NULL, action TEXT NOT NULL, idempotency_key TEXT NOT NULL, "
            "request TEXT NOT NULL, response TEXT NOT NULL, data TEXT NOT NULL, "
            "state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "operator_address TEXT, nonce TEXT, "
            "raw_transaction BLOB, authorization TEXT, lease_token TEXT, lease_until REAL, "
            "UNIQUE(payment_id,idempotency_key))",
            "CREATE UNIQUE INDEX IF NOT EXISTS payment_one_terminal ON payment_operations "
            "(payment_id) WHERE action IN ('capture','void','reclaim') "
            "AND state NOT IN ('failed','invalidated')",
            "CREATE UNIQUE INDEX IF NOT EXISTS payment_one_funding ON payment_operations "
            "(payment_id) WHERE action='fund' AND state NOT IN ('failed','invalidated')",
            "CREATE TABLE IF NOT EXISTS payment_effects (payment_id TEXT NOT NULL, "
            "kind TEXT NOT NULL, operation_id TEXT NOT NULL UNIQUE, evidence TEXT NOT NULL, "
            "PRIMARY KEY(payment_id,kind))",
            "CREATE TABLE IF NOT EXISTS payment_observations (id INTEGER PRIMARY KEY, "
            "operation_id TEXT NOT NULL, observed_at TEXT NOT NULL, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS payment_nonce_heads (chain_id INTEGER NOT NULL, "
            "operator_address TEXT NOT NULL, next_nonce TEXT NOT NULL, "
            "PRIMARY KEY(chain_id,operator_address))",
            "CREATE TABLE IF NOT EXISTS payment_worker_schedule ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton=1), active_turns INTEGER NOT NULL)",
            "INSERT OR IGNORE INTO payment_worker_schedule VALUES (1,0)",
        )
        for statement in statements:
            db.execute(statement)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def create_payment(db, payment: PaymentAccount):
        row = db.execute(
            "SELECT data FROM payment_accounts WHERE payment_id=?", (payment.payment_id,)
        ).fetchone()
        if row:
            stored = PaymentAccount.model_validate_json(row[0])
            if (stored.order_id, stored.snapshot_id, stored.terms) != (
                payment.order_id,
                payment.snapshot_id,
                payment.terms,
            ):
                raise DomainError(409, "accepted payment terms are immutable")
            return stored
        if payment.payment_id != payment.terms.payment_id:
            raise DomainError(409, "payment ID differs from accepted terms")
        try:
            db.execute(
                "INSERT INTO payment_accounts VALUES (?,?,?,?,?)",
                (
                    payment.payment_id,
                    payment.order_id,
                    payment.snapshot_id,
                    payment.terms.model_dump_json(),
                    payment.model_dump_json(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise DomainError(409, "order already has a payment account") from error
        return payment

    @staticmethod
    def payment(db, payment_id):
        row = db.execute(
            "SELECT data FROM payment_accounts WHERE payment_id=?", (payment_id,)
        ).fetchone()
        if row is None:
            raise DomainError(404, "payment not found")
        return PaymentAccount.model_validate_json(row[0])

    @classmethod
    def payment_terms(cls, db, payment_id):
        return cls.payment(db, payment_id).terms

    @classmethod
    def save_payment(cls, db, payment):
        original = cls.payment(db, payment.payment_id)
        if (original.terms, original.order_id, original.snapshot_id) != (
            payment.terms,
            payment.order_id,
            payment.snapshot_id,
        ):
            raise DomainError(409, "accepted payment terms are immutable")
        db.execute(
            "UPDATE payment_accounts SET data=? WHERE payment_id=?",
            (payment.model_dump_json(), payment.payment_id),
        )

    @classmethod
    def reserve(cls, db, operation: PaymentOperation, private_authorization=None):
        intent = operation.intent
        payment = cls.payment(db, intent.payment_id)
        if (
            operation.operation_id != intent.operation_id
            or intent.order_id != payment.order_id
            or intent.snapshot_id != payment.snapshot_id
            or intent.binding.snapshot_id != payment.snapshot_id
            or intent.mode != payment.terms.mode
            or intent.chain_id != payment.terms.chain_id
            or intent.payment_hash.lower() != payment.terms.payment_hash.lower()
            or intent.amount_atomic != payment.terms.amount_atomic
        ):
            raise DomainError(409, "operation does not match immutable accepted payment")
        canonical = intent.model_dump(mode="json", exclude={"operation_id"})
        request = _json(
            {
                "intent": canonical,
                "fingerprint": operation.fingerprint,
                "authorization_hash": hashlib.sha256(private_authorization.encode()).hexdigest()
                if private_authorization is not None
                else None,
            }
        )
        row = db.execute(
            "SELECT request,response FROM payment_operations WHERE payment_id=? "
            "AND idempotency_key=?",
            (intent.payment_id, intent.idempotency_key),
        ).fetchone()
        if row:
            if row[0] != request:
                raise DomainError(409, "idempotency key reused with changed payment request")
            return PaymentOperation.model_validate_json(row[1])
        if (
            operation.state != "reserved"
            or operation.transaction_hash
            or operation.nonce is not None
        ):
            raise DomainError(409, "new operations must be unsubmitted reservations")
        try:
            db.execute(
                "INSERT INTO payment_operations "
                "(operation_id,payment_id,action,idempotency_key,request,response,data,state,"
                "created_at,updated_at,authorization) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation.operation_id,
                    intent.payment_id,
                    intent.action,
                    intent.idempotency_key,
                    request,
                    operation.model_dump_json(),
                    operation.model_dump_json(),
                    operation.state,
                    operation.created_at.isoformat(),
                    operation.updated_at.isoformat(),
                    private_authorization,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise DomainError(
                409, "payment already has an active or confirmed operation"
            ) from error
        return operation

    @staticmethod
    def get(db, operation_id):
        row = db.execute(
            "SELECT data FROM payment_operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None:
            raise DomainError(404, "payment operation not found")
        return PaymentOperation.model_validate_json(row[0])

    @staticmethod
    def by_idempotency(db, payment_id, key):
        row = db.execute(
            "SELECT data FROM payment_operations WHERE payment_id=? AND idempotency_key=?",
            (payment_id, key),
        ).fetchone()
        return PaymentOperation.model_validate_json(row[0]) if row else None

    @staticmethod
    def operations(db, payment_id):
        return tuple(
            PaymentOperation.model_validate_json(row[0])
            for row in db.execute(
                "SELECT data FROM payment_operations WHERE payment_id=? "
                "ORDER BY created_at,operation_id",
                (payment_id,),
            ).fetchall()
        )

    @staticmethod
    def terminal(db, payment_id):
        row = db.execute(
            "SELECT data FROM payment_operations WHERE payment_id=? "
            "AND action IN ('capture','void','reclaim') AND state NOT IN ('failed','invalidated')",
            (payment_id,),
        ).fetchone()
        return PaymentOperation.model_validate_json(row[0]) if row else None

    @staticmethod
    def pending(db, limit=20, include_confirmed=False, *, now=None):
        now = now or datetime.now(UTC)
        active = db.execute(
            "SELECT p.data FROM payment_operations p "
            "WHERE p.state IN ('reserved','signed','submitted','uncertain') "
            "AND (p.lease_until IS NULL OR p.lease_until<=?) "
            "ORDER BY p.updated_at,p.operation_id LIMIT ?",
            (now.timestamp(), limit),
        ).fetchall()
        audits = []
        if include_confirmed:
            # Only the latest receipt is audited, no more than once per minute.
            # Active submissions/observations share a fair queue ahead of routine audits.
            audits = db.execute(
                "SELECT p.data FROM payment_operations p WHERE p.state='confirmed' "
                "AND json_extract(p.data,'$.intent.mode')!='mock' AND p.updated_at<=? "
                "AND (p.lease_until IS NULL OR p.lease_until<=?) "
                "AND NOT EXISTS (SELECT 1 FROM payment_operations n "
                "WHERE n.payment_id=p.payment_id AND n.rowid>p.rowid "
                "AND n.state NOT IN ('failed','invalidated')) "
                "ORDER BY p.updated_at,p.operation_id LIMIT ?",
                (
                    (now - timedelta(seconds=AUDIT_INTERVAL_SECONDS)).isoformat(),
                    now.timestamp(),
                    limit,
                ),
            ).fetchall()
        turns = db.execute(
            "SELECT active_turns FROM payment_worker_schedule WHERE singleton=1"
        ).fetchone()[0]
        rows = []
        while len(rows) < limit and (active or audits):
            if audits and (not active or turns >= ACTIVE_TURNS_PER_AUDIT):
                rows.append(audits.pop(0))
                turns = 0
            else:
                rows.append(active.pop(0))
                turns += 1
        return tuple(PaymentOperation.model_validate_json(row[0]) for row in rows)

    @classmethod
    def update(cls, db, operation_id, **changes):
        operation = cls.get(db, operation_id)
        changes.setdefault("updated_at", datetime.now(UTC))
        changed = PaymentOperation.model_validate({**operation.model_dump(), **changes})
        db.execute(
            "UPDATE payment_operations SET data=?,state=?,updated_at=? WHERE operation_id=?",
            (
                changed.model_dump_json(),
                changed.state,
                changed.updated_at.isoformat(),
                operation_id,
            ),
        )
        return changed

    @classmethod
    def invalidate(cls, db, payment_id, binding=None):
        invalidated = []
        for operation in cls.operations(db, payment_id):
            if operation.state not in ("reserved", "signed"):
                continue
            if binding is not None and operation.intent.binding == binding:
                continue
            invalidated.append(cls.invalidate_operation(db, operation.operation_id))
        return tuple(invalidated)

    @classmethod
    def invalidate_operation(cls, db, operation_id, reason=None):
        operation = cls.get(db, operation_id)
        if operation.state not in ("reserved", "signed"):
            raise DomainError(409, "submitted operations require reconciliation, not cancellation")
        cls.release_unused_nonce(db, operation_id)
        return cls.update(
            db,
            operation_id,
            state="invalidated",
            error=reason or "order binding or settlement eligibility changed before submission",
        )

    @classmethod
    def release_unused_nonce(cls, db, operation_id):
        operation = cls.get(db, operation_id)
        if operation.state not in ("reserved", "signed") or operation.nonce is None:
            return
        _, _, operator = cls.private(db, operation_id)
        # Single unresolved operation per signer makes this a safe tail rollback.
        db.execute(
            "UPDATE payment_nonce_heads SET next_nonce=? WHERE chain_id=? "
            "AND operator_address=? AND next_nonce=?",
            (str(operation.nonce), operation.intent.chain_id, operator, str(operation.nonce + 1)),
        )

    @staticmethod
    def private(db, operation_id):
        """Internal capability access; never include this result in an API or report."""
        row = db.execute(
            "SELECT raw_transaction,authorization,operator_address FROM payment_operations "
            "WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if row is None:
            raise DomainError(404, "payment operation not found")
        return row

    @staticmethod
    def claim(db, operation_id, lease_seconds=120):
        now = datetime.now(UTC).timestamp()
        token = str(uuid4())
        changed = db.execute(
            "UPDATE payment_operations SET lease_token=?,lease_until=? WHERE operation_id=? "
            "AND state IN ('reserved','signed','submitted','uncertain','confirmed') "
            "AND (lease_until IS NULL OR lease_until<=?)",
            (token, now + lease_seconds, operation_id, now),
        ).rowcount
        if changed:
            # Charge successful claims, not advisory selections. Persist the fair share
            # across restarts; this counter carries no financial authority or bookings.
            db.execute(
                "UPDATE payment_worker_schedule SET active_turns=CASE "
                "WHEN (SELECT state FROM payment_operations WHERE operation_id=?)='confirmed' "
                "THEN 0 ELSE MIN(active_turns+1,?) END WHERE singleton=1",
                (operation_id, ACTIVE_TURNS_PER_AUDIT),
            )
        return token if changed else None

    @staticmethod
    def renew_claim(db, operation_id, token, lease_seconds=120, *, activity="prepare"):
        """Extend only a strictly current owner, never revive an expired/finished activity."""
        states = {
            "prepare": ("reserved", "signed"),
            "submit": ("submitted",),
            "inspect": ("submitted", "uncertain", "confirmed"),
        }[activity]
        now = datetime.now(UTC).timestamp()
        placeholders = ",".join("?" for _ in states)
        return bool(
            db.execute(
                "UPDATE payment_operations SET lease_until=MAX(lease_until,?) "
                "WHERE operation_id=? AND lease_token=? AND lease_until>? "
                f"AND state IN ({placeholders})",
                (now + lease_seconds, operation_id, token, now, *states),
            ).rowcount
        )

    @staticmethod
    def owns(db, operation_id, token):
        row = db.execute(
            "SELECT lease_token,lease_until FROM payment_operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        return bool(
            row
            and token
            and row[0] == token
            and row[1] is not None
            and row[1] > datetime.now(UTC).timestamp()
        )

    @staticmethod
    def release_claim(db, operation_id, token):
        db.execute(
            "UPDATE payment_operations SET lease_token=NULL,lease_until=NULL "
            "WHERE operation_id=? AND lease_token=?",
            (operation_id, token),
        )

    @classmethod
    def reserve_nonce(cls, db, operation_id, operator, pending_nonce):
        operation = cls.get(db, operation_id)
        if operation.nonce is not None:
            return operation.nonce
        operator = operator.lower()
        # One unresolved transaction per dedicated signer prevents nonce gaps when an
        # unsubmitted reservation is invalidated and limits recovery to one transaction.
        blocker = db.execute(
            "SELECT operation_id FROM payment_operations WHERE operator_address=? "
            "AND operation_id<>? AND nonce IS NOT NULL "
            "AND state NOT IN ('confirmed','failed','invalidated') LIMIT 1",
            (operator, operation_id),
        ).fetchone()
        if blocker:
            return None
        row = db.execute(
            "SELECT next_nonce FROM payment_nonce_heads WHERE chain_id=? AND operator_address=?",
            (operation.intent.chain_id, operator),
        ).fetchone()
        nonce = max(pending_nonce, int(row[0]) if row else 0)
        db.execute(
            "INSERT INTO payment_nonce_heads VALUES (?,?,?) ON CONFLICT(chain_id,operator_address) "
            "DO UPDATE SET next_nonce=excluded.next_nonce",
            (operation.intent.chain_id, operator, str(nonce + 1)),
        )
        db.execute(
            "UPDATE payment_operations SET operator_address=?,nonce=? WHERE operation_id=?",
            (operator, str(nonce), operation_id),
        )
        cls.update(db, operation_id, nonce=nonce)
        return nonce

    @classmethod
    def save_signed(cls, db, operation_id, signed):
        operation = cls.get(db, operation_id)
        if operation.state != "reserved" or operation.nonce != signed.nonce:
            raise DomainError(409, "operation changed before signed transaction persistence")
        _, _, operator = cls.private(db, operation_id)
        if operator.lower() != signed.sender.lower():
            raise DomainError(409, "transaction signer differs from reserved nonce owner")
        db.execute(
            "UPDATE payment_operations SET raw_transaction=? WHERE operation_id=?",
            (signed.raw_transaction, operation_id),
        )
        return cls.update(
            db,
            operation_id,
            state="signed",
            transaction_hash=signed.transaction_hash,
            attempts=operation.attempts + 1,
        )

    @staticmethod
    def record_observation(db, operation_id, evidence):
        db.execute(
            "INSERT INTO payment_observations (operation_id,observed_at,data) VALUES (?,?,?)",
            (operation_id, datetime.now(UTC).isoformat(), _json(evidence)),
        )

    @staticmethod
    def last_block(db, operation_id):
        for row in db.execute(
            "SELECT data FROM payment_observations WHERE operation_id=? ORDER BY id DESC",
            (operation_id,),
        ):
            evidence = json.loads(row[0])
            block = evidence.get("block_evidence", evidence)
            if block.get("block_hash") is not None and block.get("block_number") is not None:
                return int(block["block_number"]), block["block_hash"].lower()
        return None

    @classmethod
    def confirm(cls, db, operation_id, evidence, callback=None):
        operation = cls.get(db, operation_id)
        terms = cls.payment_terms(db, operation.intent.payment_id)
        changes = {"state": "confirmed", "reconciliation_status": "confirmed", "error": None}
        if operation.intent.mode == "mock":
            if not evidence.get("simulated") or operation.transaction_hash:
                raise DomainError(409, "mock confirmation requires explicit simulation")
        else:
            block = BlockEvidence.model_validate(evidence.get("block_evidence", evidence))
            expected_event = {
                "fund": "PaymentAuthorized",
                "capture": "PaymentCaptured",
                "void": "PaymentVoided",
                "reclaim": "PaymentReclaimed",
            }
            if (
                block.transaction_hash != operation.transaction_hash
                or not block.canonical
                or block.confirmations < terms.confirmations
                or block.payment_hash.lower() != terms.payment_hash.lower()
                or block.amount_atomic != terms.amount_atomic
                or block.event != expected_event[operation.intent.action]
            ):
                raise DomainError(
                    409, "chain evidence does not confirm this full payment operation"
                )
            changes["block_evidence"] = block
            if evidence.get("observation") is not None:
                changes["observation"] = evidence["observation"]
        if operation.state in ("failed", "invalidated", "orphaned"):
            raise DomainError(409, "held or finished operation requires explicit recovery")
        kind = "fund" if operation.intent.action == "fund" else "terminal"
        existing = db.execute(
            "SELECT operation_id FROM payment_effects WHERE payment_id=? AND kind=?",
            (operation.intent.payment_id, kind),
        ).fetchone()
        if existing and existing[0] != operation_id:
            raise DomainError(409, "payment effect already booked by another operation")
        confirmed = cls.update(db, operation_id, **changes)
        cls.record_observation(db, operation_id, evidence)
        if existing is None:
            db.execute(
                "INSERT INTO payment_effects VALUES (?,?,?,?)",
                (operation.intent.payment_id, kind, operation_id, _json(evidence)),
            )
            if callback is not None:
                callback(db, confirmed, evidence)
        return confirmed

    @classmethod
    def complete_mock(cls, db, operation_id, callback=None):
        operation = cls.get(db, operation_id)
        if operation.intent.mode != "mock":
            raise DomainError(409, "live payment cannot use simulated completion")
        return cls.confirm(db, operation_id, {"simulated": True}, callback)
