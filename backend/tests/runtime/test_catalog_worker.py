"""Offline orchestration evidence using temporary stores, clocks and blocked-call events."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.agents.compiler import OfflineCompiler
from app.contracts.catalog import (
    AnswerCommand,
    ApprovalCommand,
    Assessment,
    Clarification,
    ClarifyCommand,
    CompilerOutput,
    Provenance,
    RequestCommand,
    RevisionCommand,
)
from app.contracts.payments import FundingAuthorization
from app.orders.catalog import CatalogService
from app.runtime.catalog_worker import CatalogWorker
from app.storage.catalog import CatalogRepository
from tests.catalog.fixtures import accepted, cmd, repaired, upload
from tests.catalog.test_approvals import require_approval
from tests.catalog.test_disputes import dispute


class Interrupted(BaseException):
    """Simulate loss of the process after the service commits a reservation."""


def restart(service, clock, **kwargs):
    return CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock, **kwargs
    )


def request(service, prompt="storage under 2 kg unit price no more than USD 40", key="request"):
    return service.create_request(
        RequestCommand(prompt=prompt, corpus_id="storage-2026", idempotency_key=key)
    )


def clean_order(service, fixtures):
    service.registry.register(fixtures["repair"].model_copy(update={"version": 5}))
    return accepted(service)


def test_compiles_initial_and_answered_drafts_automatically(setup):
    service, clock, _ = setup
    contexts = []

    class Compiler:
        def compile(self, context):
            contexts.append(context)
            return OfflineCompiler().compile(context)

    service.compiler = Compiler()
    draft = request(service)
    worker = CatalogWorker(service)
    assert worker.run_once()
    question = service.get_request(draft.request_id)
    assert question.status == "clarification" and question.compiler_calls == 1
    assert not worker.run_once()
    clock.advance(10)
    service.clarify(
        draft.request_id,
        ClarifyCommand(
            expected_revision=question.revision,
            idempotency_key="answer",
            question_id=question.question.question_id,
            text="net unit weight",
        ),
    )
    assert CatalogWorker(restart(service, clock, compiler=Compiler())).run_once()
    ready = service.get_request(draft.request_id)
    assert ready.status == "ready" and ready.compiler_calls == 2
    assert ready.deadline == draft.deadline and ready.questions_asked == 1
    assert len(contexts) == 2 and contexts[0].sources == contexts[1].sources
    assert not worker.run_once()


def test_clarification_round_limit_and_deadline_are_not_reset(setup):
    service, clock, _ = setup

    class Compiler:
        def compile(self, context):
            return CompilerOutput(
                terms=None,
                question=Clarification(
                    question_id=f"q-{context.draft.compiler_calls}",
                    field="weight",
                    prompt="Which weight?",
                ),
                summary="Clarification required",
                limitations=(),
            )

    service.compiler = Compiler()
    draft = request(service)
    worker = CatalogWorker(service)
    for i in range(3):
        assert worker.run_once()
        question = service.get_request(draft.request_id)
        assert question.questions_asked == i + 1
        clock.advance(10)
        service.clarify(
            draft.request_id,
            ClarifyCommand(
                expected_revision=question.revision,
                idempotency_key=f"answer-{i}",
                question_id=question.question.question_id,
                text="Please clarify",
            ),
        )
    assert worker.run_once()
    final = service.get_request(draft.request_id)
    assert final.status == "human_review" and final.compiler_calls == 4
    assert final.questions_asked == 3 and final.deadline == draft.deadline
    assert not worker.run_once()


def test_interrupted_compilations_spend_budget_across_restart(setup):
    service, clock, _ = setup
    calls = []

    class Compiler:
        def compile(self, context):
            calls.append(context.draft.compiler_calls)
            raise Interrupted()

    draft = request(service)
    for attempt in range(1, 5):
        worker = CatalogWorker(restart(service, clock, compiler=Compiler()))
        with pytest.raises(Interrupted):
            worker.run_once()
        reserved = service.get_request(draft.request_id)
        assert reserved.compiler_calls == attempt and reserved.status == "compiling"
        assert not CatalogWorker(restart(service, clock)).run_once()
        clock.advance(45)
    assert not CatalogWorker(restart(service, clock, compiler=Compiler())).run_once()
    clock.advance(120)  # An uncertain final call retains its original deadline.
    assert CatalogWorker(restart(service, clock, compiler=Compiler())).run_once()
    final = service.get_request(draft.request_id)
    assert final.status == "human_review" and final.compiler_calls == 4
    assert final.deadline == draft.deadline and calls == [1, 2, 3, 4]
    with service.repository.transaction() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM catalog_compile_dispatch WHERE outcome='uncertain'"
            ).fetchone()[0]
            == 4
        )


def test_unowned_internal_compile_reservation_is_observed_before_retry(setup):
    service, clock, _ = setup

    class Compiler:
        def compile(self, _context):
            raise Interrupted()

    service.compiler = Compiler()
    draft = request(service)
    with pytest.raises(Interrupted):
        service.compile_request(
            draft.request_id,
            RevisionCommand(
                expected_revision=draft.revision,
                idempotency_key="manual-interrupted",
            ),
        )
    worker = CatalogWorker(restart(service, clock))
    assert worker.run_once()  # Observe the spent reservation, without another model call.
    assert service.get_request(draft.request_id).compiler_calls == 1
    assert not worker.run_once()
    clock.advance(45)
    assert worker.run_once()
    result = service.get_request(draft.request_id)
    assert result.status == "clarification" and result.compiler_calls == 2


def test_competing_compilers_wait_for_lease_and_reject_late_result(setup):
    service, clock, _ = setup
    entered, release = Event(), Event()

    class Slow:
        def compile(self, context):
            entered.set()
            assert release.wait(5)
            return OfflineCompiler().compile(context)

    service.compiler = Slow()
    draft = request(service)
    first = CatalogWorker(service)
    second = CatalogWorker(restart(service, clock))
    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(first.run_once)
        try:
            assert entered.wait(3)
            assert not second.run_once()
            clock.advance(45)
            assert second.run_once()
            current = service.get_request(draft.request_id)
            assert current.status == "clarification" and current.compiler_calls == 2
        finally:
            release.set()
        assert future.result(3)
    assert service.get_request(draft.request_id) == current


def test_compiler_completion_after_deadline_never_applies(setup):
    service, clock, _ = setup

    class Late:
        def compile(self, context):
            clock.advance(300)
            return OfflineCompiler().compile(context)

    service.compiler = Late()
    draft = request(service)
    worker = CatalogWorker(service)
    assert worker.run_once()
    final = service.get_request(draft.request_id)
    assert final.status == "human_review" and final.compiler_calls == 1
    assert final.deadline == draft.deadline and final.specification is None
    assert not worker.run_once()


def test_default_service_pauses_until_explicit_mock_funding_is_processed(setup):
    fixture_service, clock, _ = setup
    service = restart(fixture_service, clock)
    order = accepted(service)
    worker = CatalogWorker(service)
    assert not worker.run_once()
    assert service.get(order.snapshot.order_id).jobs[0].attempts == 0
    prepared = service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
    pending = service.payments.authorize(
        order.snapshot.order_id,
        FundingAuthorization(
            expected_revision=order.revision,
            expected_binding=order.binding.model_dump(),
            idempotency_key="authorize",
            funding_attempt_id=prepared.funding_attempt_id,
            payment_hash=prepared.terms.payment_hash,
            simulate=True,
        ),
    )
    assert not worker.run_once() and pending.authorization.status == "pending"
    assert service.payments.work(limit=1).processed == 1
    assert worker.run_once()
    waiting = service.get(order.snapshot.order_id)
    assert waiting.order_state == "waiting_evidence" and waiting.jobs[0].attempts == 1
    assert not waiting.deliveries and not waiting.ledger
    assert not worker.run_once()


def test_evidence_and_both_consents_gate_automatic_resumption(setup):
    service, clock, fixtures = setup
    order = require_approval(service, accepted(service))
    worker = CatalogWorker(service)
    assert worker.run_once()
    waiting = service.get(order.snapshot.order_id)
    assert not worker.run_once()
    upload(service, waiting, fixtures["repair"].artifact)
    assert worker.run_once()
    pending = service.get(order.snapshot.order_id)
    assert pending.order_state == "pending_approval" and not worker.run_once()
    approval = pending.approvals[-1]
    customer = service.mutate(
        order.snapshot.order_id,
        "approval_customer",
        cmd(
            pending,
            "customer",
            ApprovalCommand,
            approval_id=approval.approval_id,
            actor="customer:test",
            accept=True,
        ),
    )
    assert not worker.run_once()
    clock.advance(5)
    approved = service.mutate(
        order.snapshot.order_id,
        "approval_provider",
        cmd(
            customer,
            "provider",
            ApprovalCommand,
            approval_id=approval.approval_id,
            actor="ignored",
            accept=True,
        ),
        actor="provider:test",
    )
    assert approved.repair_deadline == waiting.repair_deadline
    assert worker.run_once()
    delivered = service.get(order.snapshot.order_id)
    assert delivered.verification.passed and len(delivered.deliveries) == 1
    assert delivered.snapshot == order.snapshot and not delivered.ledger
    assert not CatalogWorker(restart(service, clock)).run_once()


def test_competing_workers_and_expired_lease_publish_once(setup, monkeypatch):
    import app.orders.catalog as catalog

    service, clock, fixtures = setup
    order = clean_order(service, fixtures)
    original = catalog.produce
    entered, release = Event(), Event()

    def slow(*args):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(catalog, "produce", slow)
    first = CatalogWorker(service)
    second = CatalogWorker(restart(service, clock))
    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(first.run_once)
        try:
            assert entered.wait(3)
            assert not second.run_once()
            clock.advance(45)
            assert second.run_once()
            delivered = service.get(order.snapshot.order_id)
            assert len(delivered.deliveries) == 1 and delivered.jobs[0].attempts == 2
        finally:
            release.set()
        assert future.result(3)
    assert service.get(order.snapshot.order_id) == delivered
    assert not CatalogWorker(restart(service, clock)).run_once()
    assert not delivered.ledger


def test_interrupted_job_attempts_exhaust_without_extending_authority(setup, monkeypatch):
    service, clock, fixtures = setup
    order = clean_order(service, fixtures)

    def crash(*_args):
        raise Interrupted()

    monkeypatch.setattr("app.orders.catalog.produce", crash)
    for attempt in range(1, 4):
        worker = CatalogWorker(restart(service, clock))
        with pytest.raises(Interrupted):
            worker.run_once()
        current = service.get(order.snapshot.order_id)
        assert current.jobs[0].attempts == attempt and not current.deliveries
        assert not CatalogWorker(restart(service, clock)).run_once()
        clock.advance(45)
    assert CatalogWorker(restart(service, clock)).run_once()
    failed = service.get(order.snapshot.order_id)
    assert failed.order_state == "human_review" and failed.jobs[0].attempts == 3
    assert failed.authorization.expires_at == order.authorization.expires_at
    assert not failed.deliveries and not failed.ledger


def test_injected_assessor_findings_resume_after_answer_without_new_delivery(setup):
    service, clock, fixtures = setup
    calls = []

    class Assessor:
        def assess_obligation(self, obligation, claim, evidence):
            calls.append((obligation, claim, evidence))
            return Assessment(
                obligation_id=obligation.obligation_id,
                result="UNKNOWN",
                reason_code="MISSING_FACT",
                explanation="Need a supplier source",
                missing_facts=("source",),
                requested_evidence="Supply the source passage",
                citations=tuple(p.citation for p in evidence),
                provenance=Provenance(kind="deterministic", assessor="offline-test", version="1"),
            )

    order = dispute(service, repaired(service, fixtures))
    service.investigator.assessor = Assessor()
    worker = CatalogWorker(service)
    for index in range(2):
        assert worker.run_once()
        current = service.get(order.snapshot.order_id)
        assert current.cases[-1].questions_asked == index + 1
        assert len(current.semantic_findings) == index + 1
        assert not worker.run_once()
        clock.advance(1)
        service.mutate(
            order.snapshot.order_id,
            "answer",
            cmd(
                current,
                f"answer-{index}",
                AnswerCommand,
                text="No further evidence",
            ),
        )
    assert worker.run_once()
    final = service.get(order.snapshot.order_id)
    assert final.order_state == "human_review" and len(calls) == 3
    assert final.cases[-1].deadline == order.cases[-1].deadline
    assert final.deliveries == order.deliveries and not final.ledger
    assert all(bundle for _, _, bundle in calls)
    assert all(
        service.store.resolve(p.citation, final.artifacts) == p.text
        for _, _, bundle in calls
        for p in bundle
    )


def test_answer_invalidates_inflight_semantic_result(setup):
    service, clock, fixtures = setup
    order = dispute(service, repaired(service, fixtures))
    worker = CatalogWorker(service)
    assert worker.run_once()
    waiting = service.get(order.snapshot.order_id)
    # A previously queued recheck races the user's answer to the current question.
    with service.repository.transaction() as db:
        service._enqueue(waiting, "reverify")
        service._save(db, waiting)
    entered, release = Event(), Event()

    class Assessor:
        def assess_obligation(self, obligation, claim, evidence):
            entered.set()
            assert release.wait(5)
            return Assessment(
                obligation_id=obligation.obligation_id,
                result="FAIL",
                reason_code="LATE_FINDING",
                explanation="Old answer was unsupported",
                citations=tuple(p.citation for p in evidence),
                provenance=Provenance(kind="deterministic", assessor="offline-test", version="1"),
            )

    service.investigator.assessor = Assessor()
    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(worker.run_once)
        try:
            assert entered.wait(3)
            running = service.get(order.snapshot.order_id)
            answered = service.mutate(
                order.snapshot.order_id,
                "answer",
                cmd(
                    running,
                    "new-answer",
                    AnswerCommand,
                    text="Additional source information",
                ),
            )
        finally:
            release.set()
        assert future.result(3)
    current = service.get(order.snapshot.order_id)
    assert current == answered and current.cases[-1].status == "open"
    assert all(f.reason_code != "LATE_FINDING" for f in current.semantic_findings)
    assert current.cases[-1].deadline == waiting.cases[-1].deadline
    assert current.deliveries == waiting.deliveries and not current.ledger
    assert CatalogWorker(restart(service, clock)).run_once()


def test_failed_pdf_attempt_waits_for_service_retry_command(setup, monkeypatch):
    import app.orders.catalog as catalog

    service, _, fixtures = setup
    order = clean_order(service, fixtures)
    original = catalog.produce

    def failure(*_args):
        raise OSError("Synthetic PDF failure")

    monkeypatch.setattr(catalog, "produce", failure)
    worker = CatalogWorker(service)
    assert worker.run_once()
    failed = service.get(order.snapshot.order_id)
    assert failed.order_state == "operational_failure" and failed.jobs[-1].attempts == 1
    assert not failed.deliveries and not worker.run_once()
    service.mutate(order.snapshot.order_id, "retry", cmd(failed, "retry"))
    monkeypatch.setattr(catalog, "produce", original)
    assert worker.run_once()
    delivered = service.get(order.snapshot.order_id)
    assert len(delivered.deliveries) == 1 and delivered.jobs[0].status == "failed"
    assert delivered.authorization.expires_at == order.authorization.expires_at
