"""Additive profile records in jobflow's database, never a second financial ledger."""

import json

from app.contracts.jobflow import Event
from app.investigation.documents import extract_document
from app.storage.jobflow import DomainError, canonical, uid


def migrate(store):
    with store.connect(write=True) as db:
        db.execute("CREATE TABLE IF NOT EXISTS br_drafts(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS br_orders(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS br_assessment_attempts (id TEXT PRIMARY KEY, "
            "order_id TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL UNIQUE, status TEXT NOT NULL, "
            "request_json TEXT NOT NULL, raw_response_json TEXT, candidate_json TEXT, "
            "validation_json TEXT, failure TEXT, latency_seconds REAL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS br_assessment_work (id TEXT PRIMARY KEY, "
            "order_id TEXT NOT NULL, actor_id TEXT NOT NULL, causal_id TEXT NOT NULL, "
            "binding_json TEXT NOT NULL, resume INTEGER NOT NULL, status TEXT NOT NULL, "
            "attempt_id TEXT, failure TEXT, UNIQUE(actor_id,causal_id))"
        )


def get(db, table, identifier, model):
    if table not in {"br_drafts", "br_orders"}:
        raise ValueError("unsupported profile table")
    row = db.execute(f"SELECT body FROM {table} WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise DomainError("Profile record not found", 404)
    return model.model_validate_json(row[0])


def save(db, table, record):
    if table not in {"br_drafts", "br_orders"}:
        raise ValueError("unsupported profile table")
    db.execute(
        f"INSERT INTO {table} VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
        (record.id, record.model_dump_json()),
    )


def event(db, entity_id, actor_id, causal_id, now, event_type, **payload):
    sequence = db.execute(
        "SELECT COALESCE(MAX(sequence),0)+1 FROM jf_events WHERE order_id=?", (entity_id,)
    ).fetchone()[0]
    item = Event(
        id=uid("event"),
        sequence=sequence,
        order_id=entity_id,
        case_id=payload.get("issue_id") or entity_id,
        causal_id=causal_id,
        timestamp=now,
        actor_id=actor_id,
        type=event_type,
        payload=payload,
    )
    db.execute("INSERT INTO jf_events VALUES(?,?,?)", (entity_id, sequence, item.model_dump_json()))
    return item


def artifact(db, entity_id, raw, filename, media_type, actor_id, now, kind):
    extraction = extract_document(raw, filename, media_type)
    identifier = uid("artifact")
    metadata = {
        "id": identifier,
        "version": 1,
        "sha256": extraction["sha256"],
        "filename": filename,
        "media_type": media_type,
        "kind": kind,
        "origin_actor_id": actor_id,
        "created_at": now.isoformat(),
    }
    db.execute(
        "INSERT INTO jf_artifacts VALUES(?,?,?,?,?)",
        (identifier, entity_id, canonical(metadata), raw, canonical(extraction)),
    )
    return metadata


def events(db, entity_id, after=0):
    return [
        json.loads(row[0])
        for row in db.execute(
            "SELECT body FROM jf_events WHERE order_id=? AND sequence>? ORDER BY sequence",
            (entity_id, after),
        )
    ]
