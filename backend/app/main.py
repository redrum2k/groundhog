import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.orders import router, worker
from app.orders.service import DomainError, OrderService, utc_now
from app.payments import configured_payment_mode
from app.storage.orders import OrderRepository

logger = logging.getLogger(__name__)


def create_app(
    database_path: Path | None = None,
    *,
    internal_token: str | None = None,
    artifact_root: Path | None = None,
    clock=utc_now,
    run_worker: bool = True,
) -> FastAPI:
    mode = configured_payment_mode()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.orders = OrderService(
            OrderRepository(
                database_path or Path(os.getenv("ORDER_DB_PATH", "artifacts/orders.sqlite3"))
            ),
            clock,
        )
        app.state.internal_token = internal_token or os.getenv("INTERNAL_API_TOKEN")
        app.state.artifact_root = artifact_root or Path(os.getenv("ARTIFACT_ROOT", "artifacts"))

        async def sweep():
            while True:
                try:
                    await asyncio.to_thread(app.state.orders.expire_due)
                except Exception:
                    logger.exception("Review deadline sweep failed; persisted work will be retried")
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

    app = FastAPI(title="Invoice order to cash", version="0.2.0", lifespan=lifespan)
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

    @app.exception_handler(ValueError)
    async def invalid_operation(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "payment_mode": mode, "live_settlement_enabled": False}

    app.include_router(router)
    app.include_router(worker)
    return app


app = create_app()
