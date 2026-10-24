"""The jobflow domain, journal, bytes and work queue share one SQLite database."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from app.contracts.jobflow import Event, OrderView


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class DomainError(Exception):
    def __init__(self, detail: str, status: int = 409):
        super().__init__(detail)
        self.detail = detail
        self.status = status


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jf_orders(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_events(
                    order_id TEXT NOT NULL, sequence INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(order_id, sequence));
                CREATE TABLE IF NOT EXISTS jf_artifacts(
                    id TEXT PRIMARY KEY, order_id TEXT NOT NULL, metadata TEXT NOT NULL,
                    raw BLOB NOT NULL, extraction TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_receipts(
                    actor_id TEXT NOT NULL, key TEXT NOT NULL, request TEXT NOT NULL,
                    response TEXT NOT NULL, PRIMARY KEY(actor_id, key));
                CREATE TABLE IF NOT EXISTS jf_work(
                    id TEXT PRIMARY KEY, order_id TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, request TEXT NOT NULL, result TEXT);
                CREATE TABLE IF NOT EXISTS jf_provider_results(
                    operation_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_postings(
                    business_event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_actors(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_sessions(
                    token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL, expires_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jf_model_calls(
                    run_id TEXT PRIMARY KEY, request TEXT NOT NULL, reserved_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS jf_work_request_immutable
                    BEFORE UPDATE OF id, order_id, kind, request ON jf_work
                    BEGIN SELECT RAISE(ABORT, 'immutable execution intent'); END;
            """)
            for table in (
                "jf_events",
                "jf_artifacts",
                "jf_receipts",
                "jf_provider_results",
                "jf_postings",
                "jf_model_calls",
            ):
                for verb in ("UPDATE", "DELETE"):
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{verb.lower()}
                        BEFORE {verb} ON {table}
                        BEGIN SELECT RAISE(ABORT, 'immutable record'); END""")

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, order_id):
        row = db.execute("SELECT body FROM jf_orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise DomainError("Order not found", 404)
        return OrderView.model_validate_json(row[0])

    @staticmethod
    def save(db, order):
        db.execute(
            "INSERT INTO jf_orders VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
            (order.id, order.model_dump_json()),
        )

    @staticmethod
    def event(db, order, actor, causal_id, now, kind, **payload):
        order.last_event_sequence += 1
        event = Event(
            id=uid("event"),
            order_id=order.id,
            case_id=order.case_id,
            sequence=order.last_event_sequence,
            causal_id=causal_id,
            timestamp=now,
            actor_id=actor,
            type=kind,
            job_id=payload.get("job_id"),
            attempt_id=payload.get("attempt_id"),
            payload=payload,
        )
        db.execute(
            "INSERT INTO jf_events VALUES(?,?,?)",
            (
                order.id,
                event.sequence,
                event.model_dump_json(),
            ),
        )

    @staticmethod
    def replay(db, actor_id, key, request):
        row = db.execute(
            "SELECT request,response FROM jf_receipts WHERE actor_id=? AND key=?", (actor_id, key)
        ).fetchone()
        if row is None:
            return None
        if row["request"] != canonical(request):
            raise DomainError("Idempotency key already belongs to a different request")
        return json.loads(row["response"])

    @staticmethod
    def receipt(db, actor_id, key, request, response):
        db.execute(
            "INSERT INTO jf_receipts VALUES(?,?,?,?)",
            (
                actor_id,
                key,
                canonical(request),
                canonical(response),
            ),
        )

    @staticmethod
    def enqueue(db, operation_id, order_id, kind, request):
        db.execute(
            "INSERT INTO jf_work VALUES(?,?,?,?,?,NULL)",
            (
                operation_id,
                order_id,
                kind,
                "QUEUED",
                canonical(request),
            ),
        )

    @staticmethod
    def artifact(db, order_id, source_id):
        row = db.execute(
            "SELECT * FROM jf_artifacts WHERE id=? AND order_id=?", (source_id, order_id)
        ).fetchone()
        if row is None:
            raise DomainError("Artifact not found", 404)
        metadata = json.loads(row["metadata"])
        raw = bytes(row["raw"])
        if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
            raise DomainError("Artifact integrity check failed")
        return raw, metadata, json.loads(row["extraction"])
