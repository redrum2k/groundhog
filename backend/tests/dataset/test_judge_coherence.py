"""Connected default/mock path: grounded findings, not keyword-selected verdicts."""

import pytest

from app.investigation.dataset import semantic_attempt
from app.orders.runs import Runs
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import command, delivered
from tests.dataset.test_review_boundary import client_for


@pytest.mark.parametrize(
    "text,field,product",
    [
        (
            "Yoga is included in our agreed scope, "
            "and these totals are double-counted across ZIPs.",
            "category",
            "dataset",
        ),
        ("ZIP 94110 is present but contains duplicate gym and app users.", "coverage", "94110"),
    ],
)
def test_unexpected_composite_complaint_is_not_dismissed_by_keyword(
    dataset_service, text, field, product
):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        response = client.post(
            f"/orders/{order.snapshot.order_id}/disputes",
            json={
                **command(order, "unexpected-objection").model_dump(mode="json"),
                "complaint": {
                    "artifact_id": order.deliveries[-1].csv.artifact_id,
                    "requirement_id": "R-" + field.upper(),
                    "field": field,
                    "product_id": product,
                    "text": text,
                },
            },
        )
        assert response.status_code == 200
    assert CatalogWorker(service).run_once()
    current = service.get(order.snapshot.order_id)
    assert current.semantic_findings[-1].result == "UNKNOWN"
    assert current.cases[-1].status != "unsupported" and not current.ledger
    assert current.snapshot == order.snapshot
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
        assert attempt and attempt.effective.result == "UNKNOWN"
        assert attempt.order_id == current.snapshot.order_id
    page = Runs(service).page(current.snapshot.quote.request_id)
    while not page.caught_up:
        page = Runs(service).page(current.snapshot.quote.request_id, page.next_after)
    # Complete event stream remains available; a no-proof result is unresolved.
    with service.repository.transaction() as db:
        verdicts = [
            r[0]
            for r in db.execute(
                "SELECT body FROM run_events WHERE run_id=? AND body LIKE '%\"verdict\"%'",
                (current.snapshot.quote.request_id,),
            )
        ]
    assert any('"unresolved"' in body and attempt.attempt_id in body for body in verdicts)


def test_rule_disposition_has_durable_order_bound_assessment(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        response = client.post(
            f"/orders/{order.snapshot.order_id}/disputes",
            json={
                **command(order, "known-objection").model_dump(mode="json"),
                "complaint": {
                    "artifact_id": order.deliveries[-1].csv.artifact_id,
                    "requirement_id": "R-COVERAGE",
                    "field": "coverage",
                    "product_id": "94110",
                    "text": "ZIP 94110 is missing from the CSV.",
                },
            },
        )
        assert response.status_code == 200
    CatalogWorker(service).run_once()
    current = service.get(order.snapshot.order_id)
    assert current.cases[-1].status == "unsupported" and not current.ledger
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
        assert attempt and attempt.effective.result == "FAIL"
        assert attempt.effective.provenance.kind == "deterministic"
        assert attempt.accepted_specification_sha256


def test_wrong_delivered_values_are_rejected_then_corrected_once_via_worker_api(
    dataset_service, monkeypatch
):
    import csv
    import io

    from fastapi.testclient import TestClient

    from app.datasets import produce_dataset
    from app.main import create_app
    from tests.dataset.conftest import accepted, fund

    service, _ = dataset_service
    order = fund(service, accepted(service))
    calls = []

    def corrupt_once(terms, sources, store):
        output, preview = produce_dataset(terms, sources, store)
        calls.append(True)
        if len(calls) == 1:
            rows = list(csv.DictReader(store.read(output).decode().splitlines()))
            row = next(row for row in rows if row["status"] == "released")
            row["count"] = str(int(row["count"]) + 17)
            changed = io.StringIO(newline="")
            writer = csv.DictWriter(changed, fieldnames=("zip", "area", "count", "status"))
            writer.writeheader()
            writer.writerows(rows)
            output = store.put(changed.getvalue().encode(), "text/csv")
        return output, preview

    monkeypatch.setattr("app.orders.dataset.produce_dataset", corrupt_once)
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=service.clock,
        run_worker=False,
        payment_mode="mock",
        internal_token="test-worker",
    )
    with TestClient(app) as client:
        path = f"/internal/orders/{order.snapshot.order_id}/work"
        rejected = client.post(path, headers={"X-Internal-Token": "test-worker"})
        assert rejected.status_code == 200
        first = rejected.json()["order"]
        assert not first["deliveries"] and not first["ledger"]
        assert first["free_corrections_used"] == 1
        assert any(not report["passed"] for report in first["verification_history"])
        for expected_status in (200, 409):
            response = client.post(path, headers={"X-Internal-Token": "test-worker"})
            assert response.status_code == expected_status, response.text
        final = client.get(f"/orders/{order.snapshot.order_id}").json()["order"]
        assert final["verification"]["passed"] and len(final["deliveries"]) == 1
        assert final["free_corrections_used"] == 1 and not final["ledger"] and len(calls) == 2


def test_default_assessment_survives_interruption_and_public_worker_retry(
    dataset_service, monkeypatch
):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.dataset.test_lifecycle import dispute

    class InterruptedAfterAssessment(BaseException):
        pass

    service, clock = dataset_service
    original = dispute(
        service,
        delivered(service),
        text="Cross-ZIP duplicate users may inflate these totals.",
        field="cohort",
    )

    def crash(*args, **kwargs):
        raise InterruptedAfterAssessment()

    with monkeypatch.context() as patch:
        patch.setattr(service, "complete_verification", crash)
        with pytest.raises(InterruptedAfterAssessment):
            service.run_one(original.snapshot.order_id)
    claimed = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        saved = semantic_attempt(db, claimed)
    assert saved and saved.effective.result == "UNKNOWN" and not claimed.semantic_findings
    clock.advance(45)
    app = create_app(
        service.repository.path,
        artifact_root=service.store.root,
        clock=clock,
        run_worker=False,
        payment_mode="mock",
        internal_token="test-worker",
    )
    with TestClient(app) as client:
        for expected_status in (200, 409):
            response = client.post(
                f"/internal/orders/{original.snapshot.order_id}/work",
                headers={"X-Internal-Token": "test-worker"},
            )
            assert response.status_code == expected_status, response.text
        current = client.get(f"/orders/{original.snapshot.order_id}").json()["order"]
    assert current["snapshot"] == original.snapshot.model_dump(mode="json")
    assert current["cases"][-1]["deadline"] == original.cases[-1].deadline.isoformat().replace(
        "+00:00", "Z"
    )
    assert current["cases"][-1]["questions_asked"] == 1
    assert len(current["semantic_findings"]) == 1 and not current["ledger"]
    with service.repository.transaction() as db:
        rows = db.execute(
            "SELECT data FROM catalog_records WHERE kind='dataset_assessment'"
        ).fetchall()
    assert len(rows) == 1
