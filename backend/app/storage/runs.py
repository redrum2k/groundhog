"""Transactional append-only canvas effects beside the existing order and payment store."""

from app.contracts.runs import EVENT_ADAPTER
from app.orders.service import DomainError


class RunEvents:
    def __init__(self, repository):
        with repository.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, order_id TEXT UNIQUE)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS run_events (run_id TEXT NOT NULL, seq "
                "INTEGER NOT NULL, effect_key TEXT NOT NULL, body TEXT NOT NULL, "
                "PRIMARY KEY(run_id,seq), UNIQUE(run_id,effect_key))"
            )
            db.execute(
                "CREATE TRIGGER IF NOT EXISTS run_events_no_update BEFORE UPDATE "
                "ON run_events BEGIN SELECT RAISE(ABORT,'run events are "
                "immutable'); END"
            )
            db.execute(
                "CREATE TRIGGER IF NOT EXISTS run_events_no_delete BEFORE DELETE "
                "ON run_events BEGIN SELECT RAISE(ABORT,'run events are "
                "immutable'); END"
            )

    @staticmethod
    def append(db, run_id, key, now, **event):
        existing = db.execute(
            "SELECT body FROM run_events WHERE run_id=? AND effect_key=?", (run_id, key)
        ).fetchone()
        if existing:
            return EVENT_ADAPTER.validate_json(existing[0])
        seq = db.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        item = EVENT_ADAPTER.validate_python({"seq": seq, "at": now, "track": "shared", **event})
        db.execute(
            "INSERT INTO run_events VALUES(?,?,?,?)",
            (run_id, seq, key, item.model_dump_json(by_alias=True)),
        )
        return item

    @staticmethod
    def identity(db, run_id):
        row = db.execute("SELECT order_id FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise DomainError(404, "run not found")
        return row[0]

    @staticmethod
    def page(db, run_id, after, limit=100):
        RunEvents.identity(db, run_id)
        high = db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        if after > high:
            raise DomainError(409, "cursor is ahead of this run; restart from after=0")
        events = [
            EVENT_ADAPTER.validate_json(r[0])
            for r in db.execute(
                "SELECT body FROM run_events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?",
                (run_id, after, limit),
            )
        ]
        return events, high
