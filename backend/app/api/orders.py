import hashlib
import json
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from app.contracts.api import (
    AcceptQuote,
    CreateOrder,
    Mutation,
    OpenDispute,
    OrderView,
    PublishDelivery,
    QuoteRequest,
    ReportFailure,
    SubmitAnswer,
    SubmitInvestigation,
)
from app.contracts.models import InvestigationInput
from app.orders.service import DomainError, OrderService

router = APIRouter()


def service(request: Request) -> OrderService:
    return request.app.state.orders


Service = Annotated[OrderService, Depends(service)]


def require_worker(request: Request, x_internal_token: Annotated[str | None, Header()] = None):
    expected = request.app.state.internal_token
    if not expected:
        raise DomainError(503, "trusted worker endpoints require INTERNAL_API_TOKEN")
    if not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise DomainError(403, "invalid trusted worker token")


worker = APIRouter(prefix="/internal", dependencies=[Depends(require_worker)])


@router.post("/orders", response_model=OrderView, status_code=201)
def create_order(command: CreateOrder, orders: Service):
    return orders.view(orders.create(command))


@router.get("/orders/{order_id}", response_model=OrderView)
def get_order(order_id: str, orders: Service, response: Response):
    order = orders.get(order_id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"{order.revision}"'
    return orders.view(order)


@router.post("/orders/{order_id}/acceptance", response_model=OrderView)
def accept(order_id: str, command: Mutation, orders: Service):
    return orders.view(orders.mutate(order_id, "accept", command))


@router.post("/orders/{order_id}/disputes", response_model=OrderView)
def dispute(order_id: str, command: OpenDispute, orders: Service):
    return orders.view(orders.mutate(order_id, "dispute", command))


@router.post("/orders/{order_id}/answers", response_model=OrderView)
def answer(order_id: str, command: SubmitAnswer, orders: Service):
    return orders.view(orders.mutate(order_id, "answer", command))


@router.post("/orders/{order_id}/quote-acceptance", response_model=OrderView)
def accept_quote(order_id: str, command: AcceptQuote, orders: Service):
    return orders.view(orders.mutate(order_id, "accept_quote", command))


@worker.post("/orders/{order_id}/deliveries", response_model=OrderView)
def publish(order_id: str, command: PublishDelivery, orders: Service):
    return orders.view(orders.mutate(order_id, "delivery", command))


@worker.post("/orders/{order_id}/failures", response_model=OrderView)
def failure(order_id: str, command: ReportFailure, orders: Service):
    return orders.view(orders.mutate(order_id, "failure", command))


@worker.get("/orders/{order_id}/investigation-input", response_model=InvestigationInput)
def investigation_input(order_id: str, orders: Service):
    return orders.investigation_input(orders.get(order_id))


@worker.post("/orders/{order_id}/investigations", response_model=OrderView)
def investigation(order_id: str, command: SubmitInvestigation, orders: Service):
    return orders.view(orders.mutate(order_id, "investigation", command))


@worker.post("/orders/{order_id}/quotes", response_model=OrderView)
def quote(order_id: str, command: QuoteRequest, orders: Service):
    return orders.view(orders.mutate(order_id, "quote", command))


@router.get("/orders/{order_id}/evidence/{evidence_id}/content")
def evidence_content(
    order_id: str, evidence_id: str, version: int, request: Request, orders: Service
):
    order = orders.get(order_id)
    evidence = next(
        (
            item
            for item in order.evidence
            if item.evidence_id == evidence_id and item.version == version
        ),
        None,
    )
    if evidence is None:
        raise DomainError(404, "evidence version is not available to this order")
    if evidence.kind == "customer_evidence":
        answer = next((answer for answer in order.answers if answer.evidence == evidence), None)
        payload = (
            {"question_id": answer.question_id, "text": answer.text}
            if answer
            else {"complaint": order.complaint, "refund_requested": order.refund_requested}
        )
        data = json.dumps(payload, sort_keys=True).encode()
    else:
        root: Path = request.app.state.artifact_root.resolve()
        path = (root / evidence.storage_key).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise DomainError(404, "evidence file is unavailable")
        data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != evidence.sha256:
        raise DomainError(409, "evidence content does not match its frozen hash")
    return Response(data, media_type=evidence.media_type, headers={"Cache-Control": "no-store"})
