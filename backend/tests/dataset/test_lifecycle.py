from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.contracts.catalog import AcceptQuoteCommand, Complaint, DisputeCommand
from app.contracts.runs import RunCreate, RunDecision, RunOffer
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.runtime.catalog_worker import CatalogWorker
from app.runtime.dataset_policy import cutoff, fits
from app.storage.catalog import CatalogRepository
from tests.dataset.conftest import accepted, command, delivered, fund


def dispute(
    service, order, text="Yoga should count as fitness", field="category", product="dataset"
):
    cmd = DisputeCommand(
        **command(order, "dispute").model_dump(),
        complaint=Complaint(
            artifact_id=order.deliveries[-1].csv.artifact_id,
            requirement_id="R-" + field.upper(),
            product_id=product,
            field=field,
            text=text,
            intent="dispute_fact",
        ),
    )
    return service.mutate(order.snapshot.order_id, "dispute", cmd, advance=False)


def test_funding_only_dispatches_once(dataset_service):
    s, _ = dataset_service
    order = accepted(s)
    assert not CatalogWorker(s).run_once()
    assert not order.deliveries and not order.ledger
    order = fund(s, order)
    assert CatalogWorker(s).run_once()
    assert not CatalogWorker(s).run_once()
    assert len(s.get(order.snapshot.order_id).deliveries) == 1


def test_yoga_uses_evidence_and_separate_price(dataset_service):
    s, _ = dataset_service
    order = dispute(s, delivered(s))
    assert CatalogWorker(s).run_once()
    order = s.get(order.snapshot.order_id)
    assert order.cases[-1].status == "unsupported"
    assert order.semantic_findings[-1].result == "FAIL"
    assert not order.ledger and not order.free_corrections_used
    for ref in order.semantic_findings[-1].citations:
        s.store.resolve(ref, order.artifacts)
    quote = Runs(s).offer(
        order.snapshot.quote.request_id,
        RunOffer(binding=binding(order), scope="yoga"),
        "yoga",
        "provider:test",
    )
    assert quote.amount.amount_minor == 25
    assert quote.payment_terms.amount_atomic == 250000
    assert len(order.children) == 0
    child = s.accept_quote(
        AcceptQuoteCommand(quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="child")
    )
    assert child.snapshot.quote.specification.terms.category == "gym_app_or_yoga"
    assert not CatalogWorker(s).run_once()
    child = fund(s, child)
    assert CatalogWorker(s).run_once()
    assert s.get(child.snapshot.order_id).deliveries
    assert Runs(s).page(quote.request_id).request.status == "accepted"


def test_oakland_is_separate_authorization(dataset_service):
    s, _ = dataset_service
    order = delivered(s)
    quote = Runs(s).offer(
        order.snapshot.quote.request_id,
        RunOffer(binding=binding(order), scope="oakland"),
        "oakland",
        "provider:test",
    )
    assert quote.amount.amount_minor == 50
    assert quote.payment_terms.amount_atomic == 500000
    assert quote.specification.terms.geography == "Oakland"
    child = s.accept_quote(
        AcceptQuoteCommand(quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="child")
    )
    assert child.payment_id != order.payment_id
    assert not child.authorization.receipt
    assert not CatalogWorker(s).run_once()


def test_late_dispatch_and_publication_never_shorten_review(dataset_service):
    s, clock = dataset_service
    order = fund(s, accepted(s))
    clock.value = cutoff(order) - timedelta(seconds=200)
    assert not fits(order, clock(), "dispatch")
    assert CatalogWorker(s).run_once()
    order = s.get(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.deliveries and not order.ledger
    assert order.authorization.status == "mock_authorized"


def test_last_moment_dispute_keeps_original_deadlines(dataset_service):
    s, clock = dataset_service
    order = delivered(s)
    review = order.deliveries[-1].review_deadline
    expiry = order.authorization.expires_at
    clock.advance(59)
    order = dispute(s, order)
    assert order.cases[-1].deadline == clock() + timedelta(seconds=60)
    clock.advance(1)
    s.expire_due()
    assert not s.get(order.snapshot.order_id).ledger
    assert order.deliveries[-1].review_deadline == review
    assert order.authorization.expires_at == expiry


def test_cutoff_equality_records_complaint_without_return(dataset_service):
    s, clock = dataset_service
    order = delivered(s)
    clock.value = cutoff(order)
    assert not fits(order, clock(), "correction")
    order = dispute(s, order)
    assert order.cases and order.order_state == "human_review"
    assert not order.ledger and order.authorization.status != "released"
    s._reserve_correction(order)
    assert order.free_corrections_used == 0


def test_reads_replay_restart_concurrency_and_cursor(dataset_service):
    s, clock = dataset_service
    api = Runs(s)
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: api.create(RunCreate(), "same").id, range(8)))
    assert len(set(ids)) == 1
    run = ids[0]
    assert api.page(run).request.status == "compiling"
    with pytest.raises(DomainError):
        api.create(RunCreate(prompt="changed"), "same")
    first = api.page(run, limit=1)
    assert not first.caught_up and not first.available_actions
    fresh = CatalogService(CatalogRepository(s.repository.path), s.store.root, clock)
    assert Runs(fresh).page(run) == api.page(run)
    with pytest.raises(DomainError) as err:
        api.page(run, after=9999)
    assert err.value.status == 409
    with pytest.raises(DomainError):
        api.page("unknown")
    order = delivered(s)
    run = order.snapshot.quote.request_id
    before = api.page(run)
    clock.advance(70)
    after = api.page(run)
    assert after.events == before.events and after.payment.payment.state == "funded"
    assert after.binding == before.binding


@pytest.mark.parametrize("action", ["approve", "reject", "ask", "escalate"])
def test_reviewer_actions_bound_and_idempotent(dataset_service, action):
    s, _ = dataset_service
    order = dispute(s, delivered(s))
    with s.repository.transaction() as db:
        s._human(order, "Review the proposed return; definition unresolved")
        order.revision += 1
        s._save(db, order)
    api = Runs(s)
    run = order.snapshot.quote.request_id
    cmd = RunDecision(action=action, binding=binding(order), reason="Review frozen evidence")
    old = api.page(run)
    ack = api.decide(run, cmd, "decision", "reviewer:test")
    assert api.decide(run, cmd, "decision", "reviewer:test") == ack
    current = api.page(run)
    with pytest.raises(DomainError):
        api.decide(run, cmd, "stale", "reviewer:test")
    assert api.page(run) == current
    assert current.binding != old.binding
    with s.repository.transaction() as db:
        saved = api.order(db, run)
    assert saved.decisions[-1].actor == "reviewer:test"
    assert not any(b.kind == "capture" for b in saved.ledger)
    if action == "approve":
        assert saved.authorization.status == "released"
    elif action == "ask":
        assert saved.cases[-1].question and saved.cases[-1].questions_asked == 1
        assert saved.cases[-1].deadline == order.cases[-1].deadline
    else:
        assert saved.order_state == "human_review"


def test_concurrent_effects_are_append_only_and_never_missed(dataset_service):
    import sqlite3

    s, _ = dataset_service
    run = Runs(s).create(RunCreate(), "concurrent").id

    def emit(index):
        with s.repository.transaction() as db:
            s.effects.message(db, run, f"effect:{index}", f"Actual test command {index}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(emit, list(range(20)) * 2))
    page = Runs(s).page(run)
    assert [e.seq for e in page.events] == list(range(1, 24))
    cursor, collected = 0, []
    while True:
        batch = Runs(s).page(run, cursor, 3)
        collected.extend(batch.events)
        cursor = batch.next_after
        if batch.caught_up:
            break
    assert collected == page.events
    with pytest.raises(sqlite3.IntegrityError), s.repository.transaction() as db:
        db.execute("DELETE FROM run_events WHERE run_id=?", (run,))
    assert Runs(s).page(run).events == page.events


@pytest.mark.parametrize(
    "stage,seconds", [("dispatch", 510), ("publication", 375), ("correction", 255)]
)
def test_budget_boundary_is_strict(dataset_service, stage, seconds):
    s, clock = dataset_service
    order = accepted(s)
    clock.value = cutoff(order) - timedelta(seconds=seconds)
    assert not fits(order, clock(), stage)
    clock.value -= timedelta(microseconds=1)
    assert fits(order, clock(), stage)


@pytest.mark.parametrize("trigger", ["sweep", "get"])
def test_intake_expiry_is_a_durable_effect(dataset_service, trigger):
    s, clock = dataset_service
    api = Runs(s)
    run = api.create(RunCreate(), "expiry").id
    before = api.page(run)
    clock.advance(301)
    assert api.page(run).events == before.events
    if trigger == "sweep":
        s.expire_due()
    else:
        s.get_request(run)
    expired = api.page(run)
    assert expired.request.status == "human_review"
    assert any(e.type == "step_waiting" and e.waitingOn == "Human review" for e in expired.events)
    s.expire_due()
    s.get_request(run)
    assert api.page(run).events == expired.events
