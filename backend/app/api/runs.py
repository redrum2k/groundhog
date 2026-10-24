from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.api.catalog import reviewer_auth, worker_auth
from app.contracts.catalog import Quote
from app.contracts.runs import (
    DecisionAcknowledgement,
    EvidenceResolution,
    RunCreate,
    RunCreated,
    RunDecision,
    RunEvidenceAnswer,
    RunOffer,
    RunPage,
)
from app.orders.runs import Runs

router = APIRouter()
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=160)]


def runs(request: Request):
    return Runs(request.app.state.orders)


Service = Annotated[Runs, Depends(runs)]


@router.post("/runs", response_model=RunCreated, status_code=201)
def create(command: RunCreate, service: Service, key: Key):
    return service.create(command, key)


@router.get("/runs/{run_id}/events", response_model=RunPage)
def events(
    run_id: str,
    service: Service,
    response: Response,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    response.headers["Cache-Control"] = "no-store"
    return service.page(run_id, after, limit)


@router.post("/runs/{run_id}/decisions", response_model=DecisionAcknowledgement)
def decide(
    run_id: str,
    command: RunDecision,
    service: Service,
    key: Key,
    actor: Annotated[str, Depends(reviewer_auth)],
):
    return service.decide(run_id, command, key, actor)


@router.post("/runs/{run_id}/offers", response_model=Quote)
def offer(
    run_id: str,
    command: RunOffer,
    service: Service,
    key: Key,
    actor: Annotated[str, Depends(worker_auth)],
):
    return service.offer(run_id, command, key, actor)


@router.post("/runs/{run_id}/answers", response_model=DecisionAcknowledgement)
def answer(run_id: str, command: RunEvidenceAnswer, service: Service, key: Key):
    return service.answer(run_id, command, key)


@router.get("/runs/{run_id}/evidence/{evidence_id:path}", response_model=EvidenceResolution)
def evidence(run_id: str, evidence_id: str, service: Service, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.resolve(run_id, evidence_id)
