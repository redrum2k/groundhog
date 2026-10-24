import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.gateway import ClaudeGateway
from app.api.catalog import reviewer, router, worker
from app.contracts.http import Capabilities, ErrorResponse
from app.orders.catalog import CatalogService
from app.orders.service import DomainError, utc_now
from app.payments import configured_payment_mode
from app.storage.catalog import CatalogRepository

logger = logging.getLogger(__name__)


def create_app(
    database_path: Path | None = None,
    *,
    internal_token=None,
    reviewer_token=None,
    artifact_root: Path | None = None,
    clock=utc_now,
    run_worker=True,
    compiler=None,
):
    mode = configured_payment_mode()

    @asynccontextmanager
    async def lifespan(app):
        selected_compiler = compiler
        if selected_compiler is None and os.getenv("ENABLE_PAID_MODELS") == "true":
            selected_compiler = ClaudeGateway(enabled=True)
        app.state.orders = CatalogService(
            CatalogRepository(
                database_path or Path(os.getenv("ORDER_DB_PATH", "artifacts/orders.sqlite3"))
            ),
            artifact_root or Path(os.getenv("ARTIFACT_ROOT", "artifacts")),
            clock,
            compiler=selected_compiler,
            assessor=selected_compiler if isinstance(selected_compiler, ClaudeGateway) else None,
        )
        app.state.internal_token = internal_token or os.getenv("INTERNAL_API_TOKEN")
        app.state.reviewer_token = reviewer_token or os.getenv("REVIEWER_API_TOKEN")
        if app.state.internal_token and app.state.internal_token == app.state.reviewer_token:
            raise ValueError("worker and reviewer credentials must be different")

        async def sweep():
            while True:
                try:
                    await asyncio.to_thread(app.state.orders.expire_due)
                    await asyncio.to_thread(app.state.orders.payments.work)
                except Exception:
                    logger.exception("Deadline recovery failed; persisted work will be retried")
                await asyncio.sleep(1)

        app.state.orders.expire_due()
        task = asyncio.create_task(sweep()) if run_worker else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="Catalog order to cash",
        version="0.4.0",
        lifespan=lifespan,
        responses={status: {"model": ErrorResponse} for status in (403, 404, 409, 422, 503)},
        separate_input_output_schemas=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["ETag"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic includes rejected input by default, which may be a buyer signature.
        issues = [{k: error[k] for k in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "request validation failed",
                "issues": issues,
            },
        )

    @app.exception_handler(ValueError)
    async def invalid_operation(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", response_model=Capabilities)
    def health():
        return Capabilities(payment_mode=mode)

    app.include_router(router)
    app.include_router(worker)
    app.include_router(reviewer)
    return app


app = create_app()
