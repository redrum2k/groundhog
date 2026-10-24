"""R5: actual executor effects plus mock-only canvas transition fixtures."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from app.contracts.runs import RunDecision
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.payments.executor import ChainObservation
from tests.dataset.conftest import accepted, command, fund
from tests.payments.test_catalog_settlement import Journey
from tests.payments.test_journal import observed


def full_page(service, run):
    api = Runs(service)
    page = api.page(run)
    events = page.events
    while not page.caught_up:
        page = api.page(run, page.next_after)
        events += page.events
    return page.model_copy(update={"events": events})


def assert_projection(service, order, state):
    page = full_page(service, order.snapshot.quote.request_id)
    assert page.payment.payment.state == state
    effects = [e for e in page.events if e.type == "payment_state_changed"]
    assert effects[-1].state == state
    assert effects[-1].payment.id == page.payment.payment.payment_id
    assert effects[-1].payment.mock == page.payment.simulated
    return page


@pytest.mark.parametrize("ending", ["voided", "uncertain", "expired_not_returned", "reorg_hold"])
def test_executor_transitions_persist_current_state_and_keep_history(dataset_service, ending):
    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    s = journey.service
    order = accepted(s, payer=journey.buyer.address)
    order, _ = journey.authorize(order)
    s.payments.work()
    order = journey.confirm(order, "fund")
    before = assert_projection(s, order, "funded")
    if ending == "voided":
        with s.repository.transaction() as db:
            s._human(order, "Injected unresolved evidence for reviewer return")
            order.revision += 1
            s._save(db, order)
        Runs(s).decide(
            order.snapshot.quote.request_id,
            RunDecision(
                action="approve",
                binding=binding(order),
                reason="Return uncaptured funds",
            ),
            "return",
            "reviewer:test",
        )
        assert_projection(s, order, "void_pending")
        assert not s.get(order.snapshot.order_id).ledger
        s.payments.work()
        order = journey.confirm(order, "void")
    elif ending == "uncertain":
        op = journey.operation(order, "fund")
        journey.chain.observations[op.transaction_hash] = ChainObservation("pending")
        s.payments.work()
    elif ending == "expired_not_returned":
        clock.advance(3601)
        s.expire_due()
    else:
        order = s.run_one(order.snapshot.order_id)
        order = journey.capture(order)
        s.payments.work()
        order = journey.confirm(order, "capture")
        assert_projection(s, order, "captured")
        op = journey.operation(order, "capture")
        journey.chain.observations[op.transaction_hash] = replace(
            observed(op, journey.view(order).payment.payment),
            canonical=False,
        )
        s.payments.work()
    final = assert_projection(s, order, ending)
    assert final.events[: len(before.events)] == before.events
    current = s.get(order.snapshot.order_id)
    ledger, sends = current.ledger, list(journey.chain.broadcasts)
    journey.restart()
    journey.service.payments.work()
    assert_projection(journey.service, order, ending)
    assert journey.current(order).ledger == ledger
    assert journey.chain.broadcasts == sends
    assert len(ledger) == (1 if ending in ("voided", "reorg_hold") else 0)
    if ending == "reorg_hold":
        assert sum(e.type == "payment_captured" for e in final.events) == 1
        assert sum(e.type == "books_posted" for e in final.events) == 1


def test_mock_transition_fixture_has_no_chain_claims(dataset_service):
    """Inject unavailable-in-mock states only to exercise the shared public projection."""
    s, _ = dataset_service
    order = s.run_one(fund(s, accepted(s, key="return")).snapshot.order_id)
    frames = []

    def record(state):
        page = assert_projection(s, order, state)
        assert page.payment.simulated and not page.payment.explorer_links
        assert all(op.transaction_hash is None for op in page.payment.operations)
        events = [
            e.model_dump(mode="json", by_alias=True)
            for e in page.events
            if e.type
            in (
                "steps_planned",
                "payment_authorized",
                "payment_captured",
                "payment_state_changed",
                "state_changed",
                "books_posted",
            )
        ]
        frames.append({"state": state, "events": events})

    def injected(state):
        with s.repository.transaction() as db:
            payment = s.payments.journal.payment(db, order.payment_id)
            s.payments._state(db, payment, state)
            order.revision += 1
            s.repository.put(db, "order", order.snapshot.order_id, order)
            s.effects.state(db, order)
        record(state)

    record("funded")
    for state in ("void_pending", "voided"):
        injected(state)
    order = s.run_one(fund(s, accepted(s, key="uncertain")).snapshot.order_id)
    record("funded")
    for state in ("uncertain", "expired_not_returned"):
        injected(state)
    order = s.run_one(fund(s, accepted(s, key="reorg")).snapshot.order_id)
    order = s.mutate(order.snapshot.order_id, "accept", command(order, "capture"), advance=False)
    record("captured")
    ledger = order.ledger
    injected("reorg_hold")
    assert order.ledger == ledger and len(ledger) == 1
    output = os.getenv("REVIEW_TRANSITION_OUTPUT")
    if output:
        Path(output).write_text(
            json.dumps(
                {
                    "evidence": (
                        "Synthetic mock projection fixture; "
                        "hold/return states injected, no RPC or transfers."
                    ),
                    "frames": frames,
                },
                indent=2,
            )
            + "\n"
        )
