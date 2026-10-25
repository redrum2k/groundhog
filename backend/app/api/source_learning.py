"""Loopback-only local demonstration; distinct owner/controller credentials."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.api.catalog import reviewer_auth, worker_auth
from app.contracts.source_learning import (
    BundleUpload,
    LearningCommand,
    LearningResult,
    LearningState,
    ResolveSource,
)
from app.learning.service import OWNER, SourceLearning
from app.orders.service import DomainError

router = APIRouter(prefix="/source-learning")


def learning(request: Request):
    service = getattr(request.app.state, "source_learning", None)
    if service is None:
        raise DomainError(503, "controlled local source learning is not enabled")
    if not request.client or request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise DomainError(403, "source learning is restricted to the local demonstration")
    return service


def owner_auth(request: Request, x_source_owner_token: Annotated[str | None, Header()] = None):
    token = getattr(request.app.state, "source_owner_token", None)
    if (
        not token
        or not x_source_owner_token
        or not secrets.compare_digest(token, x_source_owner_token)
    ):
        raise DomainError(403, "invalid simulated source-owner credential")
    return OWNER


Service = Annotated[SourceLearning, Depends(learning)]
Worker = Annotated[str, Depends(worker_auth)]
Controller = Annotated[str, Depends(reviewer_auth)]
Owner = Annotated[str, Depends(owner_auth)]


@router.get("/state", response_model=LearningState)
def state(service: Service, actor: Worker):
    return service.state()


@router.post("/sources", response_model=LearningResult)
def sources(command: BundleUpload, service: Service, actor: Worker):
    return service.publish(command, actor)


@router.post("/resolve", response_model=LearningResult)
def resolve(command: ResolveSource, service: Service, actor: Owner):
    return service.resolve(command, actor)


@router.post("/propose", response_model=LearningResult)
def propose(command: LearningCommand, service: Service, actor: Worker):
    return service.propose(command, actor)


@router.post("/qualify", response_model=LearningResult)
def qualify(command: LearningCommand, service: Service, actor: Controller):
    return service.qualify(command, actor)


@router.post("/approve", response_model=LearningResult)
def approve(command: LearningCommand, service: Service, actor: Controller):
    return service.transition(command, actor, "approve")


@router.post("/activate", response_model=LearningResult)
def activate(command: LearningCommand, service: Service, actor: Controller):
    return service.transition(command, actor, "activate")


@router.post("/revoke", response_model=LearningResult)
def revoke(command: LearningCommand, service: Service, actor: Controller):
    return service.transition(command, actor, "revoke")
