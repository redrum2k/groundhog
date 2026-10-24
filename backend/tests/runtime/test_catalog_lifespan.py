import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.agents.compiler import OfflineCompiler
from app.contracts.catalog import AcceptQuoteCommand, CatalogOrder, ClarifyCommand, RevisionCommand
from app.contracts.jobflow import OrderCreate
from app.contracts.payments import FundingAuthorization
from app.main import create_app
from app.orders.catalog import CatalogService
from app.runtime.background import background_workers
from app.storage.jobflow_lock import worker_ownership
from tests.catalog.fixtures import cmd, repaired
from tests.runtime.test_catalog_worker import request


def test_lifespan_compiles_answers_and_dispatches_confirmed_funding(setup, monkeypatch):
    service, clock, fixtures = setup
    service.registry.register(fixtures["repair"].model_copy(update={"version": 5}))
    questioned, compiled, delivered = Event(), Event(), Event()
    original_compile = CatalogService.compile_request
    original_work = CatalogService.run_one

    def compile_request(self, *args):
        result = original_compile(self, *args)
        (questioned if result.question else compiled).set()
        return result

    def run_one(self, *args):
        result = original_work(self, *args)
        if result.deliveries:
            delivered.set()
        return result

    monkeypatch.setattr(CatalogService, "compile_request", compile_request)
    monkeypatch.setattr(CatalogService, "run_one", run_one)
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=clock,
        compiler=OfflineCompiler(),
    )
    with TestClient(app):
        live = app.state.orders
        draft = request(live)
        assert questioned.wait(3)
        draft = live.get_request(draft.request_id)
        live.clarify(
            draft.request_id,
            ClarifyCommand(
                expected_revision=draft.revision,
                idempotency_key="answer",
                question_id=draft.question.question_id,
                text="net unit weight",
            ),
        )
        assert compiled.wait(3)
        draft = live.get_request(draft.request_id)
        quote = live.issue_quote(
            draft.request_id,
            RevisionCommand(
                expected_revision=draft.revision,
                idempotency_key="quote",
            ),
        )
        order = live.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id,
                customer_actor="customer:test",
                idempotency_key="accept",
            )
        )
        assert order.authorization.status == "pending" and order.jobs[0].attempts == 0
        preparation = live.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
        live.payments.authorize(
            order.snapshot.order_id,
            FundingAuthorization(
                expected_revision=order.revision,
                expected_binding=order.binding.model_dump(),
                idempotency_key="authorize",
                funding_attempt_id=preparation.funding_attempt_id,
                payment_hash=preparation.terms.payment_hash,
                simulate=True,
            ),
        )
        assert delivered.wait(4)
        result = live.get(order.snapshot.order_id)
        assert len(result.deliveries) == 1 and result.jobs[0].attempts == 1
        assert result.verification.passed and not result.ledger
        assert result.authorization.receipt.mode == "mock"


def test_slow_failing_compiler_and_payment_do_not_block_sweeps_or_invoice(
    setup, monkeypatch, caplog
):
    service, clock, fixtures = setup
    catalog = repaired(service, fixtures)
    request(service, key="slow-compilation")
    compiling, paying, invoicing = Event(), Event(), Event()
    release, catalog_swept, invoice_swept = Event(), Event(), Event()
    monkeypatch.setenv("JOBFLOW_DEMO", "1")

    class SlowFailure:
        def compile(self, _context):
            compiling.set()
            assert release.wait(8)
            raise RuntimeError("private document body and transport credential")

    def slow_payment(self, limit):
        assert limit == 1
        paying.set()
        assert release.wait(8)
        raise RuntimeError("private RPC credential")

    import app.main as main

    original_invoice = main.run_once

    async def invoice_work(service):
        result = await original_invoice(service)
        invoicing.set()
        return result

    monkeypatch.setattr(main, "run_once", invoice_work)
    monkeypatch.setattr("app.payments.catalog.CatalogPayments.work", slow_payment)
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=clock,
        compiler=SlowFailure(),
    )
    with TestClient(app) as client:
        try:
            assert compiling.wait(3) and paying.wait(3) and invoicing.wait(3)
            invoice = app.state.jobflow.create(
                app.state.jobflow.actors()[0],
                OrderCreate(
                    idempotency_key="invoice",
                    document_count=1,
                    failed_count=0,
                    disputed_field=None,
                    requested_fields=[],
                ),
            )
            original_catalog_sweep = app.state.orders.expire_due
            original_invoice_sweep = app.state.jobflow.base.expire_due

            def sweep_catalog():
                result = original_catalog_sweep()
                if clock() >= catalog.deliveries[-1].review_deadline:
                    catalog_swept.set()
                return result

            def sweep_invoice():
                result = original_invoice_sweep()
                if clock() >= invoice.base_order.order.review_deadline:
                    invoice_swept.set()
                return result

            app.state.orders.expire_due = sweep_catalog
            app.state.jobflow.base.expire_due = sweep_invoice
            clock.advance(600)
            assert catalog_swept.wait(3) and invoice_swept.wait(3)
            # Read persisted rows directly: these assertions must not advance deadlines.
            with service.repository.transaction() as db:
                current = service.repository.load(
                    db, "order", catalog.snapshot.order_id, CatalogOrder
                )
                base = app.state.jobflow.base.repository.get(db, invoice.id)
            assert current.order_state == "closed" and len(current.ledger) == 1
            assert base.payment_phase == "booked"
            assert client.get("/health").status_code == 200
            assert client.get("/api/jobflow/openapi.json").status_code == 200
        finally:
            release.set()
    assert "private" not in caplog.text and "credential" not in caplog.text
    assert "lane=payments outcome=failed error_type=RuntimeError" in caplog.text


@pytest.mark.parametrize("cancel", [False, True])
def test_shutdown_keeps_ownership_until_inflight_calls_drain(tmp_path, cancel):
    entered, exiting, release, finished = Event(), Event(), Event(), Event()
    path = tmp_path / "ownership.sqlite3"
    attempts = []

    def blocked():
        attempts.append(1)
        entered.set()
        assert release.wait(5)
        finished.set()

    async def lifecycle():
        with worker_ownership(path):
            async with background_workers((("catalog", blocked, 0.25),)):
                assert await asyncio.to_thread(entered.wait, 3)
                exiting.set()
                if cancel:
                    asyncio.current_task().cancel()
                    await asyncio.sleep(0)

    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(asyncio.run, lifecycle())
        try:
            assert exiting.wait(3)
            with pytest.raises(RuntimeError, match="already has a worker"):
                with worker_ownership(path):
                    pass
            assert not future.done() and not finished.is_set()
        finally:
            release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                future.result(3)
        else:
            future.result(3)
    assert finished.is_set() and len(attempts) == 1
    with worker_ownership(path):
        pass


def test_lane_failure_retries_without_leaking_exception_data(caplog):
    failed, swept = Event(), Event()
    calls = []

    def failure():
        calls.append(1)
        if len(calls) > 1:
            failed.set()
        raise ValueError("private body token=secret")

    async def exercise():
        async with background_workers((("payments", failure, 0), ("deadlines", swept.set, 0))):
            assert await asyncio.to_thread(failed.wait, 3)
            assert await asyncio.to_thread(swept.wait, 3)

    asyncio.run(exercise())
    assert "error_type=ValueError" in caplog.text
    assert "secret" not in caplog.text and "private body" not in caplog.text
