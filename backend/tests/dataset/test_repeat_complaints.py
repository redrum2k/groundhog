"""Resolved aggregate cases permit a new complaint without rewriting prior work."""

import pytest

from app.orders.runs import Runs
from app.runtime.catalog_policy import capture_allowed
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import command, delivered
from tests.dataset.test_review_boundary import client_for


def post(client, order, text, key):
    payload = {**command(order, key).model_dump(mode="json"), "text": text}
    return client.post(f"/orders/{order.snapshot.order_id}/complaints", json=payload)


@pytest.mark.parametrize(
    "first_text,status",
    [
        ("ZIP 94110 is missing from the delivery", "unsupported"),
        ("Does standalone yoga count?", "answered"),
    ],
)
def test_second_resolved_complaint_preserves_history_and_deadlines(
    dataset_service, first_text, status
):
    service, clock = dataset_service
    initial = delivered(service)
    run_id = initial.snapshot.quote.request_id
    with client_for(service) as client:
        assert post(client, initial, first_text, "first").status_code == 200
        assert CatalogWorker(service).run_once()
        first = service.get(initial.snapshot.order_id)
        assert first.cases[-1].status == status
        original_case = first.cases[-1]
        assert "dispute" in service.view(first).available_actions
        assert any(
            a.action == "dispute" and a.enabled
            for a in Runs(service).page(run_id).available_actions
        )
        clock.advance(5)
        response = post(client, first, "ZIP 94112 is missing from the delivery", "second")
        assert response.status_code == 200, response.text
        assert (
            post(client, first, "ZIP 94112 is missing from the delivery", "second").json()
            == response.json()
        )
        assert post(client, first, "Different complaint", "second").status_code == 409
        pending = service.get(initial.snapshot.order_id)
        assert len(pending.cases) == 2 and pending.cases[0] == original_case
        assert pending.cases[-1].case_id != original_case.case_id
        assert pending.cases[-1].status == "open"
        assert pending.deliveries == initial.deliveries
        assert pending.snapshot == initial.snapshot
        assert pending.customer_acceptance is None and not pending.ledger
        assert pending.verification is None and not capture_allowed(pending, clock())
        assert "dispute" not in service.view(pending).available_actions
        assert not any(
            a.action == "dispute" and a.enabled
            for a in Runs(service).page(run_id).available_actions
        )
        assert post(client, pending, "One more claim", "concurrent").status_code == 409
        assert CatalogWorker(service).run_once()
        resolved = service.get(initial.snapshot.order_id)
        assert resolved.cases[-1].status == "unsupported"
        assert resolved.cases[0] == original_case
        assert "dispute" in service.view(resolved).available_actions
        assert not resolved.ledger
        events = Runs(service).page(run_id).events
        assert len([event for event in events if event.type == "dispute_opened"]) == 2


def test_second_complaint_after_review_expiry_is_only_a_late_case(dataset_service):
    service, clock = dataset_service
    initial = delivered(service)
    with client_for(service) as client:
        assert post(client, initial, "ZIP 94110 is missing", "first").status_code == 200
        assert CatalogWorker(service).run_once()
        resolved = service.get(initial.snapshot.order_id)
        previous = resolved.cases[-1]
        clock.advance(61)
        assert any(
            a.action == "dispute" and a.enabled
            for a in Runs(service).page(initial.snapshot.quote.request_id).available_actions
        )
        response = post(client, resolved, "Please check the source", "late")
        assert response.status_code == 200, response.text
        late = service.get(initial.snapshot.order_id)
        assert late.cases[0] == previous
        assert late.cases[-1].status == "human_review"
        assert late.deliveries[-1].review_deadline == initial.deliveries[-1].review_deadline
        assert not any(j.status == "queued" for j in late.jobs)
        assert not late.ledger


def test_second_complaint_does_not_cancel_submitted_capture(dataset_service):
    from app.contracts.catalog import ComplaintTextCommand
    from tests.dataset.conftest import accepted
    from tests.payments.test_catalog_settlement import Journey

    journey = Journey((*dataset_service, {}))
    service = journey.service
    order, _ = journey.authorize(accepted(service, payer=journey.buyer.address))
    service.payments.work(limit=1)
    order = service.run_one(journey.confirm(order, "fund").snapshot.order_id)
    order = service.mutate(
        order.snapshot.order_id,
        "complaint",
        ComplaintTextCommand(**command(order, "first").model_dump(), text="ZIP 94110 is missing"),
    )
    order = service.run_one(order.snapshot.order_id)
    assert order.cases[-1].status == "unsupported"
    first = order.cases[-1]
    order = service.mutate(order.snapshot.order_id, "accept", command(order, "accept"))
    service.payments.work(limit=1)
    submitted = journey.operation(order, "capture")
    assert submitted.state == "submitted"
    order = journey.current(order)
    assert any(
        a.action == "dispute" and a.enabled
        for a in Runs(service).page(order.snapshot.quote.request_id).available_actions
    )
    late = service.mutate(
        order.snapshot.order_id,
        "complaint",
        ComplaintTextCommand(**command(order, "second").model_dump(), text="ZIP 94112 is missing"),
    )
    assert late.cases[0] == first and late.cases[-1].status == "human_review"
    assert journey.operation(late, "capture").transaction_hash == submitted.transaction_hash
    confirmed = journey.confirm(late, "capture")
    assert confirmed.order_state == "human_review"
    assert len(confirmed.ledger) == 1
    assert journey.view(confirmed).payment.payment.state == "captured"
    assert len(journey.chain.broadcasts) == 2


@pytest.mark.parametrize("status", ["open", "human_review", "scope_change", "supported"])
def test_unresolved_or_uncorrected_case_still_blocks_another_complaint(dataset_service, status):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        assert post(client, order, "ZIP 94110 is missing", "first").status_code == 200
        with service.repository.transaction() as db:
            current = service.get(order.snapshot.order_id, db=db)
            current.cases = (current.cases[0].model_copy(update={"status": status}),)
            service._save(db, current)
        assert post(client, current, "ZIP 94112 is missing", "second").status_code == 409
