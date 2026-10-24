import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from app.contracts.catalog import ReviewCommand
from app.contracts.payments import FundingAuthorization
from app.orders.service import DomainError
from tests.catalog.fixtures import accepted, cmd, repaired


def authorize(order, preparation, *, simulate=True, signature=None):
    return FundingAuthorization(
        expected_revision=order.revision,
        expected_binding=order.binding.model_dump(),
        idempotency_key="funding",
        funding_attempt_id=preparation.funding_attempt_id,
        payment_hash=order.snapshot.quote.payment_terms.payment_hash,
        simulate=simulate,
        signature=signature,
    )


def test_wrong_payer_and_another_orders_preparation_rejected(setup):
    service, _, _ = setup
    service.auto_mock_funding = False
    first = accepted(service)
    second = accepted(service, key="second")
    preparation = service.payments.prepare(first.snapshot.order_id, cmd(first, "prepare"))
    other_buyer = Account.create()
    signature = (
        "0x"
        + Account.sign_message(
            encode_typed_data(
                full_message=preparation.typed_data.model_dump(mode="json", by_alias=True)
            ),
            other_buyer.key,
        ).signature.hex()
    )
    with pytest.raises(DomainError, match="accepted payer") as error:
        service.payments.authorize(
            first.snapshot.order_id,
            authorize(first, preparation, simulate=False, signature=signature),
        )
    assert error.value.status == 422
    with pytest.raises(DomainError, match="stale"):
        service.payments.authorize(second.snapshot.order_id, authorize(second, preparation))
    assert service.payments.work().processed == 0
    assert (
        service.view(service.get(first.snapshot.order_id)).payment.payment.state
        == "awaiting_signature"
    )


def test_reserved_funding_expires_without_dispatch_or_deadline_reset(setup):
    service, clock, _ = setup
    service.auto_mock_funding = False
    order = accepted(service)
    terms = order.snapshot.quote.payment_terms
    preparation = service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
    service.payments.authorize(order.snapshot.order_id, authorize(order, preparation))
    clock.advance(181)
    assert service.payments.work().processed == 1
    current = service.get(order.snapshot.order_id)
    view = service.view(current)
    assert current.order_state == "human_review"
    assert view.payment.payment.state == "failed"
    assert view.payment.operations[0].state == "invalidated"
    assert current.snapshot.quote.payment_terms == terms
    assert current.jobs[0].attempts == 0
    with pytest.raises(DomainError, match="dispatch requires"):
        service.claim_job(order.snapshot.order_id)
    assert service.payments.work().processed == 0


def test_capture_projection_and_failed_journal_booking_are_atomic(setup, monkeypatch):
    service, _, fixtures = setup
    order = repaired(service, fixtures)
    original = service.payments.journal.complete_mock

    def reject_capture(db, operation_id, callback=None):
        operation = service.payments.journal.get(db, operation_id)
        if operation.intent.action == "capture":
            raise DomainError(409, "synthetic journal failure")
        return original(db, operation_id, callback)

    monkeypatch.setattr(service.payments.journal, "complete_mock", reject_capture)
    with pytest.raises(DomainError, match="synthetic journal failure"):
        service.mutate(order.snapshot.order_id, "accept", cmd(order, "accept"))
    current = service.get(order.snapshot.order_id)
    assert current.ledger == () and current.customer_acceptance is None
    assert service.view(current).payment.payment.state == "funded"
    monkeypatch.setattr(service.payments.journal, "complete_mock", original)
    captured = service.mutate(current.snapshot.order_id, "accept", cmd(current, "accept"))
    payment = service.view(captured).payment
    assert captured.order_state == "closed" and payment.payment.state == "captured"
    assert [item.intent.action for item in payment.operations].count("capture") == 1
    assert all(item.transaction_hash is None for item in payment.operations)


def test_reviewer_release_projects_void_without_refund(setup):
    service, clock, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    clock.advance(120)
    order = service.get(order.snapshot.order_id)
    released = service.mutate(
        order.snapshot.order_id,
        "review",
        cmd(
            order,
            "release",
            ReviewCommand,
            action="release_authorization",
            reason="Required evidence remains unavailable.",
            supporting_evidence=(order.verification.assessments[0].citations[0],),
        ),
        actor="reviewer:test",
    )
    payment = service.view(released).payment
    assert payment.payment.state == "voided"
    assert released.ledger[-1].kind == "release"
    assert [operation.intent.action for operation in payment.operations].count("void") == 1
    assert all(operation.transaction_hash is None for operation in payment.operations)
