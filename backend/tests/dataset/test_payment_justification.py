import pytest

from app.contracts.payments import FundingAuthorization
from app.orders.payment_justification import payment_justification
from app.orders.service import DomainError
from tests.dataset.conftest import accepted, command, delivered
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_review_boundary import client_for


def test_http_justification_is_same_persisted_order_and_never_advances_it(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    before = service.current_view(order.snapshot.order_id)
    with client_for(service) as client:
        response = client.get(f"/orders/{order.snapshot.order_id}/payment-justification")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        record = response.json()
        assert record["agreement"] == order.snapshot.model_dump(mode="json")
        assert record["binding"] == order.binding.model_dump(mode="json")
        assert record["capture_eligible_now"] is False
        assert record["payment"]["simulated"] is True
    assert service.current_view(order.snapshot.order_id) == before


def test_justification_is_read_only_and_uses_current_capture_guard(dataset_service):
    service, clock = dataset_service
    order = delivered(service)
    before = service.current_view(order.snapshot.order_id)
    held = payment_justification(service, order.snapshot.order_id)
    assert not held.capture_eligible_now and held.bytes_revalidated
    assert any("review window" in b for b in held.blockers)
    assert held.exact_price == "1.00" and held.amount_atomic == "1000000"
    assert len(held.checks) == 8 and held.source_hashes and held.delivery_hashes
    assert service.current_view(order.snapshot.order_id) == before
    clock.advance(60)
    permitted = payment_justification(service, order.snapshot.order_id)
    assert permitted.capture_eligible_now and not permitted.blockers
    assert not permitted.bookings  # Reading does not sweep/settle the eligible order.
    settled = service.get(order.snapshot.order_id)
    record = payment_justification(service, order.snapshot.order_id)
    assert not record.capture_eligible_now and len(record.bookings) == 1
    assert record.bookings == settled.ledger
    assert record.bookings[0].receipt.mode == "mock"
    assert record.bookings[0].receipt.transaction_id is None


def test_unresolved_dispute_explains_hold_and_rejects_capture(dataset_service):
    service, _ = dataset_service
    order = dispute(service, delivered(service), text="Are these memberships still paid today?")
    order = service.run_one(order.snapshot.order_id)
    record = payment_justification(service, order.snapshot.order_id)
    assert not record.capture_eligible_now
    assert any("unresolved dispute" in b for b in record.blockers)
    with pytest.raises(DomainError):
        service.mutate(order.snapshot.order_id, "accept", command(order, "unauthorized"))
    assert not service.current_view(order.snapshot.order_id).order.ledger


def test_unfunded_and_pending_funding_never_look_capturable(dataset_service):
    service, _ = dataset_service
    order = accepted(service)
    record = payment_justification(service, order.snapshot.order_id)
    assert not record.capture_eligible_now and not record.bookings
    assert any("funding" in b for b in record.blockers)
    assert not record.bytes_revalidated
    prep = service.payments.prepare(order.snapshot.order_id, command(order, "prepare"))
    service.payments.authorize(
        order.snapshot.order_id,
        FundingAuthorization(
            **command(order, "fund").model_dump(),
            funding_attempt_id=prep.funding_attempt_id,
            payment_hash=prep.terms.payment_hash,
            simulate=True,
        ),
    )
    pending = payment_justification(service, order.snapshot.order_id)
    assert pending.state == "funding_pending" and not pending.capture_eligible_now
    assert not pending.bookings and not pending.delivery_hashes


def test_stale_acceptance_duplicate_and_conflicting_terminal_effects(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    stale = command(order, "stale").model_copy(update={"expected_revision": order.revision - 1})
    with pytest.raises(DomainError):
        service.mutate(order.snapshot.order_id, "accept", stale)
    assert not payment_justification(service, order.snapshot.order_id).bookings
    cmd = command(order, "accept-once")
    settled = service.mutate(order.snapshot.order_id, "accept", cmd)
    replay = service.mutate(order.snapshot.order_id, "accept", cmd)
    assert replay == settled
    assert len(payment_justification(service, order.snapshot.order_id).bookings) == 1
    with pytest.raises(DomainError, match="refund"):
        service._release(settled, service.clock())
    assert len(payment_justification(service, order.snapshot.order_id).bookings) == 1


def test_changed_artifact_cannot_be_explained_as_eligible(dataset_service, monkeypatch):
    service, clock = dataset_service
    order = delivered(service)
    clock.advance(60)
    original = service.store.read

    def corrupt(artifact):
        if artifact.artifact_id == order.deliveries[-1].csv.artifact_id:
            return b"corrupted"
        return original(artifact)

    monkeypatch.setattr(service.store, "read", corrupt)
    record = payment_justification(service, order.snapshot.order_id)
    assert not record.capture_eligible_now and not record.bytes_revalidated
    assert any("actual source/delivery bytes" in b for b in record.blockers)
    assert not record.bookings
