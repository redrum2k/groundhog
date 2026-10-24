import asyncio
import os
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.gateway import ClaudeGateway
from app.api.catalog import reviewer, router
from app.api.catalog import worker as catalog_worker
from app.api.jobflow import router as jobflow_router
from app.contracts.http import Capabilities, ErrorResponse
from app.orders.catalog import CatalogService
from app.orders.service import DomainError, utc_now
from app.payments import configured_payment_mode
from app.runtime.background import background_workers
from app.runtime.catalog_worker import CatalogWorker
from app.runtime.jobflow import Jobflow
from app.runtime.jobflow_worker import recover, run_once
from app.storage.catalog import CatalogRepository
from app.storage.jobflow import DomainError as JobflowError
from app.storage.jobflow_lock import worker_ownership


def create_app(
    database_path: Path | None = None,
    *,
    internal_token=None,
    reviewer_token=None,
    artifact_root: Path | None = None,
    clock=utc_now,
    run_worker=True,
    compiler=None,
    service=None,
    worker=None,
):
    mode = configured_payment_mode()
    if isinstance(database_path, Jobflow):
        service, database_path = database_path, None
    if service is not None:
        clock = service.clock
    if worker is not None:
        run_worker = worker

    @asynccontextmanager
    async def lifespan(app):
        path = Path(
            service.store.path
            if service
            else database_path
            or os.getenv("ORDER_DB_PATH")
            or os.getenv("JOBFLOW_DB_PATH", "artifacts/orders.sqlite3")
        )
        selected_compiler = compiler
        if selected_compiler is None and os.getenv("ENABLE_PAID_MODELS") == "true":
            selected_compiler = ClaudeGateway(enabled=True)
        app.state.orders = CatalogService(
            CatalogRepository(path),
            artifact_root or Path(os.getenv("ARTIFACT_ROOT", "artifacts")),
            clock,
            compiler=selected_compiler,
            assessor=selected_compiler if isinstance(selected_compiler, ClaudeGateway) else None,
        )
        app.state.internal_token = internal_token or os.getenv("INTERNAL_API_TOKEN")
        app.state.reviewer_token = reviewer_token or os.getenv("REVIEWER_API_TOKEN")
        if app.state.internal_token and app.state.internal_token == app.state.reviewer_token:
            raise ValueError("worker and reviewer credentials must be different")
        app.state.jobflow = service or Jobflow(
            path, demo=os.getenv("JOBFLOW_DEMO") == "1", clock=clock
        )
        jobflow_app.state.jobflow = app.state.jobflow

        def consume_jobflow():
            # Keep even synchronous invoice claim/result writes off the lifespan loop.
            try:
                return asyncio.run(run_once(app.state.jobflow))
            except Exception:
                recover(app.state.jobflow)
                raise

        ownership = worker_ownership(path) if run_worker else nullcontext()
        with ownership:
            app.state.orders.expire_due()
            if run_worker:
                recover(app.state.jobflow)
                app.state.catalog_worker = CatalogWorker(app.state.orders)
                async with background_workers(
                    (
                        ("catalog-deadlines", lambda: app.state.orders.expire_due(), 1),
                        ("invoice-deadlines", lambda: app.state.jobflow.base.expire_due(), 1),
                        ("catalog", app.state.catalog_worker.run_once, 0.25),
                        ("payments", lambda: app.state.orders.payments.work(limit=1), 0.25),
                        ("invoice", consume_jobflow, 0.25),
                    )
                ):
                    yield
            else:
                yield

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
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["ETag"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    async def jobflow_error(request: Request, exc: JobflowError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

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
    app.include_router(catalog_worker)
    app.include_router(reviewer)
    # Separate schemas retain the frozen catalog component names and the existing
    # jobflow routes despite their different OrderView and payment policies.
    jobflow_app = FastAPI(title="Invoice jobflow compatibility API", version="0.2.0")
    jobflow_app.add_exception_handler(JobflowError, jobflow_error)
    jobflow_app.add_exception_handler(DomainError, domain_error)
    jobflow_app.add_exception_handler(RequestValidationError, validation_error)
    jobflow_app.add_exception_handler(ValueError, invalid_operation)
    jobflow_app.include_router(jobflow_router)
    app.mount("/api/jobflow", jobflow_app)
    return app


app = create_app()
