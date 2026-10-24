"""Read-only run timeline. Mutations continue through existing role-checked APIs."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.contracts.run import CatalogEvent, CatalogEvents, CatalogRunSummary
from app.orders.service import DomainError

router = APIRouter()


@router.get("/", response_model=tuple[CatalogRunSummary, ...])
def runs(request: Request):
    service = request.app.state.orders
    with service.repository.transaction() as db:
        rows = db.execute(
            "SELECT data FROM catalog_run_events WHERE seq IN "
            "(SELECT max(seq) FROM catalog_run_events GROUP BY run_id) ORDER BY seq DESC LIMIT 100"
        ).fetchall()
    return tuple(
        CatalogRunSummary(
            run_id=e.run_id,
            revision=e.aggregate_revision,
            state=e.order.order_state,
            last_seq=e.seq,
        )
        for (data,) in rows
        for e in (CatalogEvent.model_validate_json(data),)
    )


@router.get("/{run_id}/events", response_model=CatalogEvents)
def events(request: Request, run_id: str, after: Annotated[int, Query(ge=0)] = 0):
    service = request.app.state.orders
    # Do not call get/current_view: those intentionally advance deadlines. Replaying
    # saved events must not create a capture or execute work, even after expiry.
    with service.repository.transaction() as db:
        if not db.execute(
            "SELECT 1 FROM catalog_records WHERE kind='order' AND id=?", (run_id,)
        ).fetchone():
            raise DomainError(404, "catalog run not found")
        rows = db.execute(
            "SELECT data FROM catalog_run_events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 100",
            (run_id, after),
        ).fetchall()
    items = tuple(CatalogEvent.model_validate_json(row[0]) for row in rows)
    return CatalogEvents(
        run_id=run_id,
        events=items,
        next_cursor=items[-1].seq if items else after,
        server_time=service.clock(),
    )
