"""Role-separated catalog improvement operations; no browser privilege tokens."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.catalog import reviewer_auth, worker_auth
from app.contracts.catalog import OrderCommand
from app.contracts.catalog_improvement import (
    CatalogImprovementCommand,
    CatalogImprovementResult,
    CatalogImprovementView,
)
from app.orders.service import DomainError

router = APIRouter()


@router.get("/scopes/{corpus_id}", response_model=CatalogImprovementView)
def view(request: Request, corpus_id: str):
    return request.app.state.procedures.view(corpus_id)


@router.post("/orders/{order_id}/observe")
def observe(
    request: Request, order_id: str, body: OrderCommand, actor: Annotated[str, Depends(worker_auth)]
):
    return {"incident_id": request.app.state.procedures.observe_order(order_id, body)}


@router.post("/commands", response_model=CatalogImprovementResult)
def command(
    request: Request, body: CatalogImprovementCommand, actor: Annotated[str, Depends(worker_auth)]
):
    if body.verb == "propose":
        return request.app.state.procedures.propose(body, actor=actor)
    if body.verb == "probe":
        return request.app.state.procedures.probe(body, actor=actor)
    raise DomainError(403, "Approval, activation and revocation use the independent reviewer route")


@router.post("/review", response_model=CatalogImprovementResult)
def review(
    request: Request, body: CatalogImprovementCommand, actor: Annotated[str, Depends(reviewer_auth)]
):
    if body.verb not in ("approve", "activate", "revoke"):
        raise DomainError(422, "This route only approves, activates or revokes")
    return request.app.state.procedures.transition(body, actor=actor)
