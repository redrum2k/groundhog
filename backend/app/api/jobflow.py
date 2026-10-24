"""The additive /api/jobflow HTTP contract."""

import io
from typing import Annotated

import pdfplumber
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.contracts.jobflow import (
    Actor,
    Command,
    DocumentUpload,
    InvestigationRequest,
    OrderCreate,
    OrderView,
)
from app.storage.jobflow import DomainError

router = APIRouter(prefix="/api/jobflow", tags=["jobflow"])


def runtime(request: Request):
    return request.app.state.jobflow


def identity(request: Request, authorization: Annotated[str | None, Header()] = None):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
    return runtime(request).authenticate(token)


Identity = Annotated[Actor, Depends(identity)]


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1, max_length=160)


def local_demo(request):
    if not runtime(request).demo:
        raise DomainError("Local demo is disabled", 404)
    if request.client and request.client.host not in {
        "127.0.0.1",
        "::1",
        "localhost",
        "testclient",
    }:
        raise DomainError("Demo session creation is local-only", 403)


@router.get("/actors", response_model=list[Actor])
def actors(request: Request):
    local_demo(request)
    return runtime(request).actors()


@router.post("/sessions")
def sessions(body: SessionRequest, request: Request):
    local_demo(request)
    return runtime(request).session(body.actor_id)


@router.get("/orders", response_model=list[OrderView])
def orders(request: Request, actor: Identity):
    return runtime(request).orders(actor)


@router.post("/orders", response_model=OrderView)
def create(body: OrderCreate, request: Request, actor: Identity):
    return runtime(request).create(actor, body)


@router.get("/orders/{order_id}", response_model=OrderView)
def view(order_id: str, request: Request, actor: Identity):
    return runtime(request).view(actor, order_id)


@router.post("/orders/{order_id}/commands", response_model=OrderView)
def command(order_id: str, body: Command, request: Request, actor: Identity):
    return runtime(request).command(actor, order_id, body)


@router.post("/orders/{order_id}/documents", response_model=OrderView)
def upload(order_id: str, body: DocumentUpload, request: Request, actor: Identity):
    return runtime(request).upload(actor, order_id, body)


@router.post("/orders/{order_id}/investigations", status_code=202)
def investigate(order_id: str, body: InvestigationRequest, request: Request, actor: Identity):
    return runtime(request).investigate(actor, order_id, body)


@router.get("/orders/{order_id}/events")
def events(order_id: str, request: Request, actor: Identity, after: int = Query(default=0, ge=0)):
    return runtime(request).events(actor, order_id, after)


@router.get("/orders/{order_id}/artifacts/{source_id}")
def artifact(order_id: str, source_id: str, request: Request, actor: Identity):
    raw, metadata, _ = runtime(request).artifact(actor, order_id, source_id)
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


@router.get("/orders/{order_id}/artifacts/{source_id}/pages/{page_number}")
def artifact_page(
    order_id: str, source_id: str, page_number: int, request: Request, actor: Identity
):
    raw, metadata, _ = runtime(request).artifact(actor, order_id, source_id)
    if metadata["media_type"] != "application/pdf" or not 1 <= page_number <= 20:
        raise DomainError("A supported PDF page is required", 422)
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if page_number > len(pdf.pages):
            raise DomainError("Page not found", 404)
        page = pdf.pages[page_number - 1]
        if page.width * page.height > 2_000_000:
            raise DomainError("PDF page dimensions exceed the rendering bound", 422)
        output = io.BytesIO()
        page.to_image(resolution=96).original.save(output, format="PNG")
    return Response(
        output.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Source-SHA256": metadata["sha256"],
        },
    )
