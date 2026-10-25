"""One customer prompt enters the same durable dispute and payment gates."""

import pytest

from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import command, delivered
from tests.dataset.test_review_boundary import client_for


def body(order, text):
    return {**command(order, "plain-complaint").model_dump(mode="json"), "text": text}


@pytest.mark.parametrize(
    "text,field,row",
    [
        ("Yoga studio members should count as fitness.", "category", "dataset"),
        ("Yoga is missing from this file.", "category", "dataset"),
        ("ZIP 94110 is missing from the CSV delivery", "coverage", "94110"),
        ("ZIP 99999 is missing from the delivery", "coverage", "dataset"),
        ("ZIP 94110 and ZIP 94112 are missing", "coverage", "dataset"),
        ("This does not look right at all.", "artifact", "dataset"),
        ("Yoga is missing and ZIP 94110 is missing.", "artifact", "dataset"),
        ("Please add Oakland to the delivery.", "geography", "dataset"),
    ],
)
def test_plain_text_is_recorded_against_frozen_targets_without_deciding_it(
    dataset_service, text, field, row
):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        url = f"/orders/{order.snapshot.order_id}/complaints"
        payload = body(order, text)
        response = client.post(url, json=payload)
        assert response.status_code == 200
        assert client.post(url, json=payload).json() == response.json()
        assert client.post(url, json={**payload, "text": "Different complaint"}).status_code == 409
    saved = service.get(order.snapshot.order_id)
    case = saved.cases[-1]
    assert len(saved.cases) == 1 and case.status == "open"
    assert case.complaint.text == text
    assert case.complaint.field == field and case.complaint.product_id == row
    assert case.complaint.intent == "dispute_fact"
    assert case.complaint.artifact_id == order.deliveries[-1].csv.artifact_id
    service.validate_dataset_complaint(saved, case.complaint)
    assert saved.snapshot == order.snapshot and not saved.children and not saved.ledger
    assert saved.delivery_state == "needs_review"
    assert saved.verification is None and saved.customer_acceptance is None
    assert any(job.kind == "reverify" and job.status == "queued" for job in saved.jobs)


def test_plain_missing_zip_claim_reaches_independent_investigation(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        assert (
            client.post(
                f"/orders/{order.snapshot.order_id}/complaints",
                json=body(order, "ZIP 94110 is missing from the delivery"),
            ).status_code
            == 200
        )
    assert CatalogWorker(service).run_once()
    saved = service.get(order.snapshot.order_id)
    assert saved.cases[-1].status == "unsupported"  # The actual delivered ZIP is present.
    assert saved.cases[-1].questions_asked == 0
    assert not saved.ledger


def test_unclear_text_stays_unresolved_instead_of_becoming_a_scope_change(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        assert (
            client.post(
                f"/orders/{order.snapshot.order_id}/complaints",
                json=body(order, "This is not what I wanted."),
            ).status_code
            == 200
        )
    assert CatalogWorker(service).run_once()
    saved = service.get(order.snapshot.order_id)
    assert saved.cases[-1].status == "open" and saved.cases[-1].question
    assert not saved.children and not saved.ledger


def test_late_text_is_recorded_without_reopening_review_or_returning_funds(dataset_service):
    service, clock = dataset_service
    order = delivered(service)
    deadline = order.deliveries[-1].review_deadline
    with client_for(service) as client:
        clock.advance(61)
        assert (
            client.post(
                f"/orders/{order.snapshot.order_id}/complaints",
                json=body(order, "Yoga should count as fitness."),
            ).status_code
            == 200
        )
    saved = service.get(order.snapshot.order_id)
    assert saved.order_state == "human_review"
    assert saved.deliveries[-1].review_deadline == deadline
    assert not saved.ledger and saved.cases[-1].status == "human_review"


@pytest.mark.parametrize(
    "change,status",
    [
        ({"text": "  "}, 422),
        ({"text": "x" * 2001}, 422),
        ({"expected_revision": 1}, 409),
        ({"intent": "change_scope"}, 422),
    ],
)
def test_invalid_or_stale_prompt_does_not_open_a_dispute(dataset_service, change, status):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        response = client.post(
            f"/orders/{order.snapshot.order_id}/complaints",
            json={**body(order, "Yoga should count as fitness."), **change},
        )
        assert response.status_code == status
    assert service.get(order.snapshot.order_id) == order
