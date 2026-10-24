import asyncio
import logging
import os
from contextlib import asynccontextmanager, nullcontext, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.jobflow import router as jobflow_router
from app.api.orders import router
from app.api.orders import worker as worker_router
from app.orders.service import DomainError, OrderService, utc_now
from app.payments import configured_payment_mode
from app.runtime.jobflow import Jobflow
from app.runtime.jobflow_worker import recover, run_once
from app.storage.jobflow import DomainError as JobflowError
from app.storage.jobflow_lock import worker_ownership
from app.storage.orders import OrderRepository

logger = logging.getLogger(__name__)


def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "payment_mode": configured_payment_mode(),
        "live_settlement_enabled": False,
    }


def create_app(
    database_path: Path | None = None,
    *,
    internal_token: str | None = None,
    artifact_root: Path | None = None,
    clock=utc_now,
    run_worker: bool = True,
    service=None,
    worker: bool | None = None,
) -> FastAPI:
    configured_payment_mode()
    if isinstance(database_path, Jobflow):
        service, database_path = database_path, None
    if service is not None:
        clock = service.clock
    if worker is not None:
        run_worker = worker

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        path = Path(
            service.store.path
            if service
            else database_path
            or os.getenv("ORDER_DB_PATH")
            or os.getenv("JOBFLOW_DB_PATH", "artifacts/orders.sqlite3")
        )
        app.state.orders = OrderService(OrderRepository(path), clock)
        app.state.jobflow = service or Jobflow(
            path, demo=os.environ.get("JOBFLOW_DEMO") == "1", clock=clock
        )
        app.state.internal_token = internal_token or os.getenv("INTERNAL_API_TOKEN")
        app.state.artifact_root = artifact_root or Path(os.getenv("ARTIFACT_ROOT", "artifacts"))
        stop = asyncio.Event()

        async def consume():
            while not stop.is_set():
                try:
                    await asyncio.to_thread(app.state.orders.expire_due)
                    if await run_once(app.state.jobflow):
                        continue
                except Exception:
                    logger.exception("Persisted workflow interrupted; recovery will retry")
                    recover(app.state.jobflow)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.25)
                except TimeoutError:
                    pass

        app.state.orders.expire_due()
        ownership = worker_ownership(path) if run_worker else nullcontext()
        with ownership:
            task = None
            if run_worker:
                recover(app.state.jobflow)
                task = asyncio.create_task(consume())
            try:
                yield
            finally:
                stop.set()
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    app = FastAPI(title="Invoice order to cash", version="0.2.0", lifespan=lifespan)
    if service:
        app.state.jobflow = service
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

    @app.exception_handler(JobflowError)
    async def jobflow_error(request: Request, exc: JobflowError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.exception_handler(ValueError)
    async def invalid_operation(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(router)
    app.include_router(worker_router)
    app.include_router(jobflow_router)
    return app


app = create_app()
