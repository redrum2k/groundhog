from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.contracts.runs import RunDecision
from app.main import create_app
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import accepted, command, fund
from tests.dataset.test_lifecycle import dispute
from tests.payments.test_catalog_settlement import Journey


def paced(service, clock):
    return CatalogService(
        service.repository, service.store.root, clock, mock_payment_delay_seconds=3
    )


def test_mock_funding_and_capture_pause_without_restarting_the_clock(dataset_service):
    original, clock = dataset_service
    service = paced(original, clock)
    order = fund(service, accepted(service))
    run_id = order.snapshot.quote.request_id
    assert Runs(service).page(run_id).payment.payment.state == "funding_pending"
    assert not order.authorization.receipt
    assert not CatalogWorker(service).run_once()
    clock.advance(2)
    service = paced(service, clock)
    assert service.payments.work().processed == 0
    clock.advance(1)
    assert service.payments.work().processed == 1
    assert Runs(service).page(run_id).payment.payment.state == "funded"
    assert CatalogWorker(service).run_once()
    order = service.get(order.snapshot.order_id)
    deadline = order.deliveries[-1].review_deadline
    acceptance = command(order, "accept-delivery")
    pending = service.mutate(order.snapshot.order_id, "accept", acceptance)
    assert Runs(service).page(run_id).payment.payment.state == "capture_pending"
    assert service.payments.work().processed == 0
    assert not service.get(order.snapshot.order_id).ledger
    clock.advance(2)
    assert service.mutate(order.snapshot.order_id, "accept", acceptance) == pending
    service = paced(service, clock)
    assert service.payments.work().processed == 0
    clock.advance(1)
    service.payments.work()
    final = service.get(order.snapshot.order_id)
    assert Runs(service).page(run_id).payment.payment.state == "captured"
    assert final.deliveries[-1].review_deadline == deadline
    assert len(final.ledger) == 1
    assert final.ledger[0].receipt.mode == "mock"
    assert final.ledger[0].receipt.transaction_id is None
    service.payments.work()
    assert len(service.get(order.snapshot.order_id).ledger) == 1
    restarted = CatalogService(service.repository, service.store.root, clock)
    assert len(restarted.get(order.snapshot.order_id).ledger) == 1
    assert len(Runs(restarted).page(run_id).payment.operations) == 2


def test_new_dispute_during_mock_capture_pause_prevents_capture(dataset_service):
    original, clock = dataset_service
    service = paced(original, clock)
    order = fund(service, accepted(service))
    clock.advance(3)
    service.payments.work()
    CatalogWorker(service).run_once()
    order = service.get(order.snapshot.order_id)
    pending = service.mutate(order.snapshot.order_id, "accept", command(order, "accept-delivery"))
    dispute(service, pending)
    clock.advance(3)
    service.payments.work()
    page = Runs(service).page(order.snapshot.quote.request_id)
    assert page.payment.payment.state == "funded"
    assert not service.get(order.snapshot.order_id).ledger
    capture = next(op for op in page.payment.operations if op.intent.action == "capture")
    assert capture.state == "invalidated"


def test_delay_does_not_override_funding_expiry(dataset_service):
    original, clock = dataset_service
    service = paced(original, clock)
    order = accepted(service)
    expiry = order.snapshot.quote.payment_terms.payment_info.pre_approval_expiry
    clock.value = datetime.fromtimestamp(expiry - 1, UTC)
    order = fund(service, order)
    clock.advance(3)
    service.payments.work()
    order = service.get(order.snapshot.order_id)
    assert order.authorization.receipt is None
    assert not CatalogWorker(service).run_once()


def test_mock_review_expiry_queues_once_and_return_is_not_delayed(dataset_service):
    original, clock = dataset_service
    service = paced(original, clock)
    order = fund(service, accepted(service))
    clock.advance(3)
    service.payments.work()
    CatalogWorker(service).run_once()
    order = service.get(order.snapshot.order_id)
    clock.value = order.deliveries[-1].review_deadline
    service.expire_due()
    service.expire_due()
    page = Runs(service).page(order.snapshot.quote.request_id)
    assert page.payment.payment.state == "capture_pending"
    assert sum(op.intent.action == "capture" for op in page.payment.operations) == 1
    clock.advance(3)
    service.payments.work()
    assert len(service.get(order.snapshot.order_id).ledger) == 1

    other = fund(service, accepted(service, key="return-order"))
    clock.advance(3)
    service.payments.work()
    other = service.get(other.snapshot.order_id)
    with service.repository.transaction() as db:
        service._human(other, "Unresolved evidence requires review")
        other.revision += 1
        service._save(db, other)
    Runs(service).decide(
        other.snapshot.quote.request_id,
        RunDecision(binding=binding(other), action="approve", reason="Return uncaptured funds"),
        "return",
        "reviewer:test",
    )
    assert Runs(service).page(other.snapshot.quote.request_id).payment.payment.state == "voided"


def test_wallet_operations_are_not_delayed(dataset_service):
    journey = Journey((*dataset_service, {}))
    service = journey.service
    service = CatalogService(
        service.repository,
        service.store.root,
        journey.clock,
        payment_mode="base_sepolia",
        payment_config=journey.config,
        payment_transport=journey.chain,
        mock_payment_delay_seconds=3,
    )
    journey.service = service
    order, _ = journey.authorize(accepted(service, payer=journey.buyer.address))
    service.payments.work()
    assert journey.operation(order, "fund").state == "submitted"
    assert len(journey.chain.broadcasts) == 1


def test_hosted_mock_delay_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PAYMENT_DELAY_SECONDS", "3")
    app = create_app(tmp_path / "db", artifact_root=tmp_path / "artifacts", run_worker=False)
    with TestClient(app):
        assert app.state.orders.payments.mock_delay_seconds == 3


@pytest.mark.parametrize("seconds", [-1, 11, 1.5, True])
def test_delay_is_bounded(dataset_service, seconds):
    service, clock = dataset_service
    with pytest.raises(ValueError, match="between 0 and 10"):
        CatalogService(
            service.repository, service.store.root, clock, mock_payment_delay_seconds=seconds
        )
