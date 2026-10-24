"""Append inside CatalogService's existing transaction; polling is strictly read-only."""

import hashlib
import json
from uuid import uuid4

from app.contracts.run import CatalogEvent


def append_catalog_event(
    db,
    order,
    payment,
    now,
    *,
    actor,
    operation,
    correlation_id=None,
    procedure_version="catalog-static-v1",
):
    body = {
        "order": order.model_dump(mode="json"),
        "payment": payment.model_dump(mode="json") if payment else None,
        "procedure_version": procedure_version,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    run_id = order.snapshot.order_id
    previous = db.execute(
        "SELECT digest FROM catalog_run_events WHERE run_id=? ORDER BY seq DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if previous and previous[0] == digest:
        return
    cursor = db.execute(
        "INSERT INTO catalog_run_events(run_id,digest,data) VALUES(?,?,?)",
        (run_id, digest, "{}"),
    )
    event = CatalogEvent(
        event_id=f"event-{uuid4().hex}",
        seq=cursor.lastrowid,
        run_id=run_id,
        occurred_at=now,
        aggregate_revision=order.revision,
        accepted_snapshot_sha256=hashlib.sha256(
            order.snapshot.model_dump_json().encode()
        ).hexdigest(),
        binding=order.binding,
        actor=actor,
        operation=operation,
        correlation_id=correlation_id,
        order=order,
        payment=payment,
        procedure_version=procedure_version,
    )
    db.execute(
        "UPDATE catalog_run_events SET data=? WHERE seq=?", (event.model_dump_json(), event.seq)
    )
