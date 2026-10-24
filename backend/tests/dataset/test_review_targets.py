"""R6: requirement/field/row consistency is enforced before creating a case."""

import pytest

from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import command, delivered
from tests.dataset.test_review_boundary import client_for


def complaint(order, **changes):
    return {
        **command(order, "complaint").model_dump(mode="json"),
        "complaint": {
            "artifact_id": order.deliveries[-1].csv.artifact_id,
            "requirement_id": "R-COVERAGE",
            "field": "coverage",
            "product_id": "94110",
            "intent": "dispute_fact",
            "text": "ZIP 94110 is missing from the delivery",
            **changes,
        },
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"requirement_id": "R-CATEGORY"},
        {"field": "category"},
        {"product_id": "unrelated-product"},
        {"field": "pdf", "requirement_id": "R-ARTIFACT"},
        {"column": "area"},
        {"product_id": "dataset", "column": "zip"},
    ],
)
def test_inconsistent_target_rejected_without_mutation(dataset_service, changes):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        response = client.post(
            f"/orders/{order.snapshot.order_id}/disputes", json=complaint(order, **changes)
        )
        assert response.status_code == 422
    assert service.get(order.snapshot.order_id) == order


def test_coverage_complaint_reaches_coverage_check(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        response = client.post(f"/orders/{order.snapshot.order_id}/disputes", json=complaint(order))
        assert response.status_code == 200
    assert CatalogWorker(service).run_once()
    case = service.get(order.snapshot.order_id).cases[-1]
    assert case.complaint.field == "coverage" and case.complaint.product_id == "94110"
    assert case.status == "unsupported" and case.questions_asked == 0


def test_explicit_scope_request_preserves_target_without_factual_question(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        body = complaint(order, intent="change_scope", column="zip")
        response = client.post(f"/orders/{order.snapshot.order_id}/disputes", json=body)
        assert response.status_code == 200
        assert (
            client.post(f"/orders/{order.snapshot.order_id}/disputes", json=body).json()
            == response.json()
        )
    assert CatalogWorker(service).run_once()
    saved = service.get(order.snapshot.order_id)
    assert saved.cases[-1].complaint.intent == "change_scope"
    assert saved.cases[-1].complaint.column == "zip"
    assert saved.cases[-1].questions_asked == 0
    assert saved.snapshot == order.snapshot and not saved.children and not saved.ledger


def test_historical_complaint_payload_still_replays(dataset_service):
    import json

    from app.contracts.catalog import DisputeCommand

    s, _ = dataset_service
    order = delivered(s)
    body = complaint(order)
    old_fingerprint = json.dumps({"operation": "dispute", "payload": body}, sort_keys=True)
    with s.repository.transaction() as db:
        s._remember_order(
            db, order.snapshot.order_id, body["idempotency_key"], old_fingerprint, order
        )
    before = s.get(order.snapshot.order_id)
    replay = s.mutate(
        order.snapshot.order_id, "dispute", DisputeCommand.model_validate(body), advance=False
    )
    assert replay == order
    assert s.get(order.snapshot.order_id) == before
