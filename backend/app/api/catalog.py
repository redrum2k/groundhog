"""Local demo API. Worker and reviewer credentials never belong in browser code."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from app.contracts.catalog import (
    AcceptQuoteCommand,
    AnswerCommand,
    ApprovalCommand,
    ClarifyCommand,
    ComplaintTextCommand,
    DisputeCommand,
    OfferCommand,
    OrderCommand,
    OrderView,
    Quote,
    QuoteRequest,
    RequestCommand,
    RequestDraft,
    ReviewCommand,
    RevisionCommand,
    Source,
    UploadCommand,
)
from app.contracts.payments import (
    FundingAuthorization,
    FundingPreparation,
    PaymentView,
    PaymentWorkResult,
)
from app.orders.catalog import CatalogService
from app.orders.service import DomainError

router = APIRouter()


def service(request: Request):
    return request.app.state.orders


Service = Annotated[CatalogService, Depends(service)]


def worker_auth(request: Request, x_internal_token: Annotated[str | None, Header()] = None):
    token = request.app.state.internal_token
    if not token:
        raise DomainError(503, "INTERNAL_API_TOKEN is not configured")
    if not x_internal_token or not secrets.compare_digest(token, x_internal_token):
        raise DomainError(403, "invalid worker credential")
    return "provider:local-worker"


def reviewer_auth(request: Request, x_reviewer_token: Annotated[str | None, Header()] = None):
    token = request.app.state.reviewer_token
    if not token:
        raise DomainError(503, "REVIEWER_API_TOKEN is not configured")
    if not x_reviewer_token or not secrets.compare_digest(token, x_reviewer_token):
        raise DomainError(403, "invalid reviewer credential")
    return "reviewer:local-trusted"


worker = APIRouter(prefix="/internal", dependencies=[Depends(worker_auth)])
reviewer = APIRouter(prefix="/reviewer", dependencies=[Depends(reviewer_auth)])


@router.get("/corpora", response_model=dict[str, tuple[Source, ...]])
def corpora(orders: Service):
    with orders.repository.transaction() as db:
        sources = [
            Source.model_validate_json(row[0])
            for row in db.execute("SELECT data FROM catalog_sources WHERE selectable=1").fetchall()
        ]
    return {
        corpus: tuple(s for s in sources if s.corpus_id == corpus)
        for corpus in sorted({s.corpus_id for s in sources})
    }


@router.post("/requests", response_model=RequestDraft, status_code=201)
def create_request(command: RequestCommand, orders: Service):
    return orders.create_request(command)


@router.get("/requests/{request_id}", response_model=RequestDraft)
def get_request(request_id: str, orders: Service):
    return orders.get_request(request_id)


@router.post("/requests/{request_id}/answers", response_model=RequestDraft)
def clarify(request_id: str, command: ClarifyCommand, orders: Service):
    return orders.clarify(request_id, command)


@worker.post("/requests/{request_id}/compile", response_model=RequestDraft)
def compile_request(request_id: str, command: RevisionCommand, orders: Service):
    return orders.compile_request(request_id, command)


@router.post("/requests/{request_id}/quotes", response_model=Quote)
def issue_quote(request_id: str, command: QuoteRequest, orders: Service):
    return orders.issue_quote(request_id, command)


@router.post("/quote-acceptance", response_model=OrderView, status_code=201)
def accept_quote(command: AcceptQuoteCommand, orders: Service):
    return orders.command_view(
        orders.accept_quote(command), command.idempotency_key, scope="acceptance"
    )


@router.get("/orders/{order_id}", response_model=OrderView)
def get_order(order_id: str, orders: Service, response: Response):
    view = orders.current_view(order_id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"{view.order.revision}"'
    return view


@router.get("/orders/{order_id}/payment", response_model=PaymentView)
def get_payment(order_id: str, orders: Service, response: Response):
    payment = orders.current_view(order_id).payment
    if payment is None:
        raise DomainError(404, "historical order has no catalog payment")
    response.headers["Cache-Control"] = "no-store"
    return payment


@router.post("/orders/{order_id}/funding-preparation", response_model=FundingPreparation)
def prepare_funding(order_id: str, command: OrderCommand, orders: Service):
    return orders.payments.prepare(order_id, command)


@router.post("/orders/{order_id}/funding-authorizations", response_model=OrderView)
def authorize_funding(order_id: str, command: FundingAuthorization, orders: Service):
    return orders.command_view(
        orders.payments.authorize(order_id, command), command.idempotency_key
    )


@worker.post("/payments/work", response_model=PaymentWorkResult)
def payment_work(orders: Service):
    return orders.payments.work()


@router.post("/orders/{order_id}/acceptance", response_model=OrderView)
def accept(order_id: str, command: OrderCommand, orders: Service):
    return orders.command_view(orders.mutate(order_id, "accept", command), command.idempotency_key)


@router.post("/orders/{order_id}/disputes", response_model=OrderView)
def dispute(order_id: str, command: DisputeCommand, orders: Service):
    return orders.command_view(orders.mutate(order_id, "dispute", command), command.idempotency_key)


@router.post("/orders/{order_id}/complaints", response_model=OrderView)
def complaint(order_id: str, command: ComplaintTextCommand, orders: Service):
    return orders.command_view(
        orders.mutate(order_id, "complaint", command), command.idempotency_key
    )


@router.post("/orders/{order_id}/answers", response_model=OrderView)
def answer(order_id: str, command: AnswerCommand, orders: Service):
    return orders.command_view(orders.mutate(order_id, "answer", command), command.idempotency_key)


@router.post("/orders/{order_id}/amendments", response_model=OrderView)
def upload(order_id: str, command: UploadCommand, orders: Service):
    return orders.command_view(orders.upload(order_id, command), command.idempotency_key)


@router.post("/orders/{order_id}/approvals", response_model=OrderView)
def customer_approval(order_id: str, command: ApprovalCommand, orders: Service):
    return orders.command_view(
        orders.mutate(order_id, "approval_customer", command), command.idempotency_key
    )


@worker.post("/orders/{order_id}/approvals", response_model=OrderView)
def provider_approval(
    order_id: str,
    command: ApprovalCommand,
    orders: Service,
    actor: Annotated[str, Depends(worker_auth)],
):
    return orders.command_view(
        orders.mutate(order_id, "approval_provider", command, actor=actor), command.idempotency_key
    )


@worker.post("/orders/{order_id}/offers", response_model=Quote)
def offer(
    order_id: str,
    command: OfferCommand,
    orders: Service,
    actor: Annotated[str, Depends(worker_auth)],
):
    return orders.offer(order_id, command, actor=actor)


@worker.post("/orders/{order_id}/work", response_model=OrderView)
def run_work(order_id: str, orders: Service):
    return orders.view(orders.run_one(order_id))


@worker.post("/orders/{order_id}/retry", response_model=OrderView)
def retry(order_id: str, command: OrderCommand, orders: Service):
    return orders.command_view(orders.mutate(order_id, "retry", command), command.idempotency_key)


@reviewer.post("/orders/{order_id}/decisions", response_model=OrderView)
def decision(
    order_id: str,
    command: ReviewCommand,
    orders: Service,
    actor: Annotated[str, Depends(reviewer_auth)],
):
    return orders.command_view(
        orders.mutate(order_id, "review", command, actor=actor), command.idempotency_key
    )


@router.get(
    "/orders/{order_id}/artifacts/{artifact_id}",
    response_class=Response,
    responses={
        200: {
            "description": "Registered immutable artifact bytes",
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {"schema": {}},
            },
        }
    },
)
def artifact(order_id: str, artifact_id: str, orders: Service):
    from app.contracts.catalog import CatalogOrder
    from app.datasets import is_dataset, public_bytes

    with orders.repository.transaction() as db:
        order = orders.repository.load(db, "order", order_id, CatalogOrder)
    evidence = next((a for a in order.artifacts if a.artifact_id == artifact_id), None)
    if not evidence:
        raise DomainError(404, "artifact not registered for this order")
    return Response(
        public_bytes(evidence, orders.store) if is_dataset(order) else orders.store.read(evidence),
        media_type=evidence.media_type,
        headers={"Cache-Control": "no-store"},
    )


@reviewer.get("/legacy/orders/{order_id}")
def historical_order(order_id: str, orders: Service):
    """Raw historical bytes retained without coercing old policies into new contracts."""
    with orders.repository.transaction() as db:
        row = db.execute("SELECT data FROM orders WHERE order_id=?", (order_id,)).fetchone()
    if not row:
        raise DomainError(404, "historical order not found")
    return Response(row[0], media_type="application/json", headers={"Cache-Control": "no-store"})


@reviewer.get("/legacy/orders/{order_id}/commands/{key}")
def historical_command(order_id: str, key: str, orders: Service):
    with orders.repository.transaction() as db:
        row = db.execute(
            "SELECT response FROM order_commands WHERE order_id=? AND idempotency_key=?",
            (order_id, key),
        ).fetchone()
    if not row:
        raise DomainError(404, "historical command not found")
    return Response(row[0], media_type="application/json", headers={"Cache-Control": "no-store"})
