"""Reviewer-controlled prospective improvement commands and immutable evidence."""

from fastapi import APIRouter, Query, Request

from app.api.jobflow import Identity
from app.contracts.improvement import ImprovementCommand, ImprovementCommandResult

router = APIRouter(tags=["improvements"])


@router.get("/")
def view(
    customer_id: str,
    request: Request,
    actor: Identity,
    product_id: str = "aggregate_regional_market_intelligence",
):
    return request.app.state.improvement.view(actor, customer_id, product_id)


@router.get("/records/{record_id}")
def record(record_id: str, request: Request, actor: Identity):
    return request.app.state.improvement.record(actor, record_id)


@router.post("/commands", response_model=ImprovementCommandResult)
async def command(body: ImprovementCommand, request: Request, actor: Identity):
    return await request.app.state.improvement.command(actor, body)


@router.get("/jobs/{job_id}")
def job(job_id: str, request: Request, actor: Identity):
    return request.app.state.improvement.job(actor, job_id)


@router.get("/entities/{entity_id}/events")
def events(entity_id: str, request: Request, actor: Identity, after: int = Query(default=0, ge=0)):
    return request.app.state.improvement.events(actor, entity_id, after)
