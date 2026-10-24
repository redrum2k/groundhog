"""Authenticated data-product profile on the existing application."""

from fastapi import APIRouter, Query, Request, Response

from app.api.jobflow import Identity
from app.contracts.broker import BrokerCommand, BrokerRecord, DraftCreate, IntakeDraft, SourceUpload

router = APIRouter(tags=["broker"])


def runtime(request):
    return request.app.state.broker


@router.post("/drafts", response_model=IntakeDraft, status_code=201)
def create(body: DraftCreate, request: Request, actor: Identity):
    return runtime(request).create_draft(actor, body)


@router.get("/drafts/{draft_id}", response_model=IntakeDraft)
def draft(draft_id: str, request: Request, actor: Identity):
    return runtime(request).draft(actor, draft_id)


@router.post("/drafts/{draft_id}/commands", response_model=IntakeDraft)
def draft_command(draft_id: str, body: BrokerCommand, request: Request, actor: Identity):
    return runtime(request).draft_command(actor, draft_id, body)


@router.post("/drafts/{draft_id}/sources", response_model=IntakeDraft)
def draft_source(draft_id: str, body: SourceUpload, request: Request, actor: Identity):
    return runtime(request).upload(actor, draft_id, body)


@router.get("/orders", response_model=list[BrokerRecord])
def orders(request: Request, actor: Identity):
    return runtime(request).orders(actor)


@router.get("/orders/{order_id}", response_model=BrokerRecord)
def view(order_id: str, request: Request, actor: Identity):
    return runtime(request).view(actor, order_id)


@router.post("/orders/{order_id}/commands", response_model=BrokerRecord)
def command(order_id: str, body: BrokerCommand, request: Request, actor: Identity):
    return runtime(request).command(actor, order_id, body)


@router.post("/orders/{order_id}/sources", response_model=BrokerRecord)
def source(order_id: str, body: SourceUpload, request: Request, actor: Identity):
    return runtime(request).upload(actor, order_id, body, accepted=True)


@router.get("/entities/{entity_id}/events")
def events(entity_id: str, request: Request, actor: Identity, after: int = Query(default=0, ge=0)):
    return runtime(request).events(actor, entity_id, after)


@router.get("/entities/{entity_id}/artifacts/{artifact_id}")
def artifact(entity_id: str, artifact_id: str, request: Request, actor: Identity):
    raw, metadata, _ = runtime(request).artifact(actor, entity_id, artifact_id)
    return Response(
        raw,
        media_type=metadata["media_type"],
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "ETag": f'"{metadata["sha256"]}"',
        },
    )
