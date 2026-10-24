"""Immutable improvement evidence and version records with a small active pointer."""

import json

from app.contracts.improvement import GreyAreaIncident, IncidentOutcome
from app.data_products import BASE_FIELDS
from app.storage.broker import event
from app.storage.jobflow import canonical, uid


def migrate(store):
    with store.connect(write=True) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS im_records(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, customer_id TEXT NOT NULL,
                product_id TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS im_state(id TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS im_active(
                customer_id TEXT NOT NULL, product_id TEXT NOT NULL, version_id TEXT NOT NULL,
                PRIMARY KEY(customer_id, product_id));
            CREATE TABLE IF NOT EXISTS im_cycles(
                id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, product_id TEXT NOT NULL,
                status TEXT NOT NULL, request TEXT NOT NULL, response TEXT);
            CREATE TRIGGER IF NOT EXISTS im_records_no_update BEFORE UPDATE ON im_records
                BEGIN SELECT RAISE(ABORT, 'immutable improvement evidence'); END;
            CREATE TRIGGER IF NOT EXISTS im_records_no_delete BEFORE DELETE ON im_records
                BEGIN SELECT RAISE(ABORT, 'immutable improvement evidence'); END;
            CREATE TRIGGER IF NOT EXISTS im_cycles_request_immutable
                BEFORE UPDATE OF id, customer_id, product_id, request ON im_cycles
                BEGIN SELECT RAISE(ABORT, 'immutable improvement intent'); END;
        """)


def put(db, kind, record):
    body = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
    db.execute(
        "INSERT INTO im_records VALUES(?,?,?,?,?)",
        (
            body["id"],
            kind,
            body["customer_id"] if "customer_id" in body else body["proposal"]["customer_id"],
            body["product_id"] if "product_id" in body else body["proposal"]["product_id"],
            canonical(body),
        ),
    )


def records(db, kind, customer_id, product_id):
    return [
        json.loads(row[0])
        for row in db.execute(
            "SELECT body FROM im_records WHERE kind=? AND customer_id=? AND product_id=? "
            "ORDER BY rowid",
            (kind, customer_id, product_id),
        )
    ]


def template(db, customer_id, product_id, version_id=None):
    if version_id is None:
        row = db.execute(
            "SELECT version_id FROM im_active WHERE customer_id=? AND product_id=?",
            (customer_id, product_id),
        ).fetchone()
        version_id = row[0] if row else "intake-v1"
    if version_id == "intake-v1":
        return {
            "id": "intake-v1",
            "required_fields": BASE_FIELDS,
            "questions": {},
            "validators": (),
            "provenance_fields": (),
        }
    row = db.execute(
        "SELECT body FROM im_records WHERE id=? AND kind='version' "
        "AND customer_id=? AND product_id=?",
        (version_id, customer_id, product_id),
    ).fetchone()
    if row is None:
        raise ValueError("template version is not available in this tenant/product scope")
    return json.loads(row[0])


def incident(
    db,
    *,
    entity_id,
    customer_id,
    product_id,
    template_version,
    cause,
    unknowns,
    now,
    sources=(),
    binding=None,
    issue_id=None,
    specification_sha256=None,
    questions=(),
    staff_touches=0,
):
    existing = records(db, "incident", customer_id, product_id)
    key = (entity_id, cause, tuple(unknowns), binding.model_dump(mode="json") if binding else None)
    for prior in existing:
        if (
            prior["entity_id"],
            prior["cause"],
            tuple(prior["material_unknowns"]),
            prior["binding"],
        ) == key:
            return prior["id"]
    item = GreyAreaIncident(
        id=uid("incident"),
        entity_id=entity_id,
        issue_id=issue_id,
        customer_id=customer_id,
        product_id=product_id,
        template_version=template_version,
        cause=cause,
        material_unknowns=tuple(unknowns),
        sources=tuple(sources),
        binding=binding,
        specification_sha256=specification_sha256,
        questions=tuple(questions),
        outcome="HELD_FOR_REVIEW",
        company_staff_touches=staff_touches,
        created_at=now,
    )
    put(db, "incident", item)
    event(
        db, entity_id, "system", item.id, now, "incident.recorded", incident_id=item.id, cause=cause
    )
    return item.id


def record_outcome(db, entity_id, customer_id, product_id, outcome, now, binding=None):
    incidents = [
        item
        for item in records(db, "incident", customer_id, product_id)
        if item["entity_id"] == entity_id
    ]
    previous = records(db, "outcome", customer_id, product_id)
    touches = sum(
        json.loads(row[0])["payload"].get("company_staff_touches", 0)
        for row in db.execute("SELECT body FROM jf_events WHERE order_id=?", (entity_id,))
    )
    for item in incidents:
        if any(
            prior["incident_id"] == item["id"] and prior["outcome"] == outcome for prior in previous
        ):
            continue
        put(
            db,
            "outcome",
            IncidentOutcome(
                id=uid("incident-outcome"),
                incident_id=item["id"],
                entity_id=entity_id,
                customer_id=customer_id,
                product_id=product_id,
                outcome=outcome,
                company_staff_touches=touches,
                binding=binding,
                created_at=now,
            ),
        )
