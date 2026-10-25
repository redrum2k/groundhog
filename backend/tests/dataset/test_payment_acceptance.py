"""Early delivery acceptance releases the review gate, never invents settlement."""

from app.orders.runs import Runs
from tests.dataset.conftest import accepted, command
from tests.payments.test_catalog_settlement import Journey


def test_early_acceptance_queues_and_confirms_capture_before_review_deadline(dataset_service):
    journey = Journey((*dataset_service, {}))
    service, clock = journey.service, journey.clock
    order, _ = journey.authorize(accepted(service, payer=journey.buyer.address))
    service.payments.work(limit=1)
    order = journey.confirm(order, "fund")
    order = service.run_one(order.snapshot.order_id)
    deadline = order.deliveries[-1].review_deadline
    clock.advance(5)
    service.payments.work(limit=1)
    assert journey.view(order).payment.payment.state == "funded"
    assert not journey.current(order).ledger
    acceptance = command(order, "accept-early")
    pending = service.mutate(order.snapshot.order_id, "accept", acceptance)
    assert pending.customer_acceptance == pending.binding
    assert pending.deliveries[-1].review_deadline == deadline
    assert journey.view(pending).payment.payment.state == "capture_pending"
    assert not pending.ledger
    assert service.mutate(order.snapshot.order_id, "accept", acceptance) == pending
    service.payments.work(limit=1)
    assert journey.operation(pending, "capture").state == "submitted"
    assert not journey.current(pending).ledger
    confirmed = journey.confirm(pending, "capture")
    assert clock() < deadline
    assert confirmed.deliveries[-1].review_deadline == deadline
    assert confirmed.order_state == "closed" and len(confirmed.ledger) == 1
    page = Runs(service).page(order.snapshot.quote.request_id)
    assert page.payment.payment.state == "captured"
    assert len(journey.chain.broadcasts) == 2
