import pytest

from app.contracts.catalog import AnswerCommand, Complaint, DisputeCommand, FulfillmentContext
from app.orders.service import DomainError

from .fixtures import cmd, repaired


def dispute(service, order, *, text="The weight is wrong", intent="dispute_fact"):
    return service.mutate(
        order.snapshot.order_id,
        "dispute",
        cmd(
            order,
            "dispute",
            DisputeCommand,
            complaint=Complaint(
                text=text,
                product_id="S01",
                field="weight",
                requirement_id="R-WEIGHT",
                artifact_id=order.deliveries[-1].pdf.artifact_id,
                intent=intent,
            ),
        ),
    )


def test_shipping_weight_complaint_is_unsupported_without_fee(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    order = dispute(service, order, text="Shipping weight exceeds the net limit")
    order = service.run_one(order.snapshot.order_id)
    assert order.cases[-1].status == "unsupported" and not order.ledger
    clock.advance(60)
    order = service.get(order.snapshot.order_id)
    assert [booking.kind for booking in order.ledger] == ["capture"]
    assert order.ledger[0].amount.amount_minor == 1500


def test_two_questions_then_escalate_and_answers_do_not_reset_deadline(setup):
    service, clock, fixtures = setup
    order = dispute(service, repaired(service, fixtures))
    deadline = order.cases[-1].deadline
    original_pdf = order.deliveries[-1].pdf
    for index in range(2):
        order = service.run_one(order.snapshot.order_id)
        assert order.cases[-1].question and order.cases[-1].questions_asked == index + 1
        clock.advance(5)
        order = service.mutate(
            order.snapshot.order_id,
            "answer",
            cmd(
                order,
                f"answer{index}",
                AnswerCommand,
                text="I cannot provide further source facts.",
            ),
        )
        assert order.cases[-1].deadline == deadline and order.deliveries[-1].pdf == original_pdf
    order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.ledger
    assert order.cases[-1].questions_asked == 2


def test_new_dispute_has_60_seconds_but_original_delivery_deadline_is_retained(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    review_deadline = order.deliveries[-1].review_deadline
    clock.advance(55)
    order = dispute(service, order)
    assert (order.cases[-1].deadline - clock()).total_seconds() == 60
    assert order.deliveries[-1].review_deadline == review_deadline
    clock.advance(60)
    order = service.get(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.ledger


def test_scope_change_is_pending_consent_not_evidence_score(setup):
    service, clock, fixtures = setup
    order = dispute(service, repaired(service, fixtures), intent="change_scope")
    order = service.run_one(order.snapshot.order_id)
    assert order.authority_state == "pending_consent"
    assert order.cases[-1].status == "scope_change" and not order.ledger
    clock.advance(60)
    assert service.get(order.snapshot.order_id).order_state == "human_review"


def test_stale_worker_result_after_customer_answer_is_rejected(setup):
    service, _, fixtures = setup
    order = dispute(service, repaired(service, fixtures))
    order = service.run_one(order.snapshot.order_id)
    # Queue a separate recheck, then answer while a worker holds the old evidence binding.
    with service.repository.transaction() as db:
        service._enqueue(order, "reverify")
        service._save(db, order)
    reserved, job = service.claim_job(order.snapshot.order_id)
    from app.catalog.verification import verify

    report, _ = verify(
        FulfillmentContext(
            snapshot=reserved.snapshot, binding=reserved.binding, sources=reserved.sources
        ),
        service.store,
        service.clock(),
        delivery=reserved.deliveries[-1].pdf,
        stage="dispute",
    )
    service.mutate(
        order.snapshot.order_id,
        "answer",
        cmd(reserved, "answer", AnswerCommand, text="Additional source facts"),
    )
    with pytest.raises(DomainError, match="stale"):
        service.complete_verification(
            order.snapshot.order_id, job, report, reserved.deliveries[-1].pdf
        )
