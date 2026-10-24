"""R7: unavailable preview bytes cannot hide durable status or prevent complaints."""

import pytest

from app.contracts.catalog import CatalogOrder, FulfillmentContext
from app.datasets import verify_dataset
from tests.dataset.conftest import command, delivered
from tests.dataset.test_review_boundary import client_for
from tests.dataset.test_review_targets import complaint


def database_dump(service):
    with service.repository.transaction() as db:
        return tuple(db.iterdump())


def stored_order(service, order_id):
    with service.repository.transaction() as db:
        return service.repository.load(db, "order", order_id, CatalogOrder)


@pytest.fixture(params=["hash_mismatch", "missing"])
def unavailable_preview(dataset_service, request):
    service, clock = dataset_service
    order = delivered(service)
    assert order.verification.passed and not order.ledger
    with client_for(service) as client:
        response = client.get(f"/runs/{order.snapshot.quote.request_id}/events")
        assert response.status_code == 200
        baseline = response.json()
    assert baseline["caught_up"]
    assert baseline["payment"]["payment"]["state"] == "funded"
    path = service.store.root / order.deliveries[-1].preview.storage_key
    if request.param == "missing":
        path.unlink()
        status = 404
    else:
        path.write_bytes(b'{"unvalidated-preview":"must-not-be-exposed"}')
        status = 409
    return service, clock, order, baseline, status


def test_faulted_preview_polling_is_bounded_read_only_and_restartable(unavailable_preview):
    service, clock, order, baseline, status = unavailable_preview
    url = f"/runs/{order.snapshot.quote.request_id}/events"
    persisted = database_dump(service)
    preview = order.deliveries[-1].preview
    path = service.store.root / preview.storage_key
    original_bytes = path.read_bytes() if path.exists() else None

    # Restart before expiry, then cross both deadlines using only HTTP reads. Startup has
    # its own deadline sweep, separate from the read-only polling contract under test.
    with client_for(service) as client:
        for seconds in (0, 61, 3600):
            clock.advance(seconds)
            cursor, events = 0, []
            while True:
                response = client.get(url, params={"after": cursor, "limit": 3})
                assert response.status_code == 200, response.text
                assert response.headers["Cache-Control"] == "no-store"
                assert "must-not-be-exposed" not in response.text
                page = response.json()
                assert 0 < len(page["events"]) <= 3
                assert page["high_watermark"] == baseline["high_watermark"]
                assert [e["seq"] for e in page["events"]] == list(
                    range(cursor + 1, page["next_after"] + 1)
                )
                assert cursor < page["next_after"] <= page["high_watermark"]
                for key in (
                    "binding",
                    "payment",
                    "reviewClosesAt",
                    "disputeClosesAt",
                    "captureClosesAt",
                    "latestSafeSubmissionAt",
                ):
                    assert page[key] == baseline[key]
                events.extend(page["events"])
                cursor = page["next_after"]
                assert database_dump(service) == persisted
                if page["caught_up"]:
                    break
                assert page["complaint_targets"] == []
                assert page["available_actions"] == []
            assert events == baseline["events"]
            assert cursor == baseline["high_watermark"]
            assert page["complaint_targets"] == baseline["complaint_targets"]
            assert any(a["action"] == "dispute" and a["enabled"] for a in page["available_actions"])
            specification = order.snapshot.quote.specification
            assert {(t["requirement_id"], t["field"]) for t in page["complaint_targets"]} == {
                (r.requirement_id, r.check) for r in specification.requirements
            }
            artifact_target = next(t for t in page["complaint_targets"] if t["field"] == "artifact")
            assert artifact_target["row_ids"] == [
                "dataset",
                *specification.terms.coverage.expected_keys,
            ]
            final = client.get(url, params={"after": cursor, "limit": 3})
            assert final.status_code == 200
            assert final.json() == {**page, "events": []}
            assert client.get(url, params={"after": cursor + 1}).status_code == 409
            assert client.get(url, params={"limit": 101}).status_code == 422
            download = client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{preview.artifact_id}"
            )
            assert download.status_code == status
            assert "must-not-be-exposed" not in download.text
            assert database_dump(service) == persisted
        assert database_dump(service) == persisted
        assert (path.read_bytes() if path.exists() else None) == original_bytes
    assert stored_order(service, order.snapshot.order_id) == order


def test_invalid_complaint_targets_still_fail_with_unavailable_preview(unavailable_preview):
    service, _, order, _, _ = unavailable_preview
    url = f"/orders/{order.snapshot.order_id}/disputes"
    body = complaint(
        order,
        requirement_id="R-ARTIFACT",
        field="artifact",
        product_id="dataset",
        text="The delivered preview is unavailable or corrupt.",
    )
    before = database_dump(service)
    with client_for(service) as client:
        for invalid in (
            {"requirement_id": "R-COVERAGE"},
            {"field": "coverage"},
            {"product_id": "unaccepted-row"},
            {"column": "zip"},
            {"intent": "capture"},
            {"artifact_id": "unrelated-artifact"},
        ):
            response = client.post(
                url, json={**body, "complaint": {**body["complaint"], **invalid}}
            )
            assert response.status_code == 422, response.text
            assert database_dump(service) == before


def test_whole_dataset_artifact_complaint_survives_fault_and_replays(unavailable_preview):
    service, clock, order, baseline, status = unavailable_preview
    url = f"/orders/{order.snapshot.order_id}/disputes"
    body = complaint(
        order,
        requirement_id="R-ARTIFACT",
        field="artifact",
        product_id="dataset",
        text="The delivered preview is unavailable or corrupt.",
    )
    with client_for(service) as client:
        response = client.post(url, json=body)
        assert response.status_code == 200, response.text
        saved = stored_order(service, order.snapshot.order_id)
        assert len(saved.cases) == 1
        assert (
            saved.cases[0].complaint.model_dump(mode="json", exclude_none=True) == body["complaint"]
        )
        assert saved.snapshot == order.snapshot and saved.deliveries == order.deliveries
        assert saved.authorization == order.authorization and not saved.ledger
        assert saved.binding.evidence_revision == order.binding.evidence_revision + 1
        assert saved.revision == order.revision + 1
        assert response.json()["payment"] == baseline["payment"]
        page = client.get(f"/runs/{order.snapshot.quote.request_id}/events").json()
        assert page["events"][: len(baseline["events"])] == baseline["events"]
        assert len(page["events"]) > len(baseline["events"])
    after = database_dump(service)
    with client_for(service) as client:
        clock.advance(61)
        replay = client.post(url, json=body)
        assert replay.status_code == 200 and replay.content == response.content
        stale = client.post(url, json={**body, "idempotency_key": "stale-complaint"})
        assert stale.status_code == 409
        changed = client.post(
            url, json={**body, "complaint": {**body["complaint"], "text": "Changed"}}
        )
        assert changed.status_code == 409
        preview = order.deliveries[-1].preview
        assert (
            client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{preview.artifact_id}"
            ).status_code
            == status
        )
        assert database_dump(service) == after


def test_unverifiable_preview_blocks_verification_and_capture(unavailable_preview):
    service, clock, order, baseline, _ = unavailable_preview
    before = database_dump(service)
    report, _ = verify_dataset(
        FulfillmentContext(snapshot=order.snapshot, binding=order.binding, sources=order.sources),
        service.store,
        clock(),
        delivery=order.deliveries[-1].csv,
        preview=order.deliveries[-1].preview,
        stage="delivery",
    )
    assert not report.passed
    assert (
        next(a for a in report.assessments if a.obligation_id == "dataset:artifact").result
        != "PASS"
    )
    assert not service.current_dataset_checks(order)
    for _ in range(2):
        with client_for(service) as client:
            response = client.post(
                f"/orders/{order.snapshot.order_id}/acceptance",
                json=command(order, "accept-unverifiable").model_dump(mode="json"),
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "capture gates do not pass"
            assert database_dump(service) == before
    # The ordinary deadline worker also refuses capture; GET did not perform this transition.
    clock.advance(60)
    service.expire_due()
    current = stored_order(service, order.snapshot.order_id)
    assert current.order_state == "human_review"
    assert not current.ledger and current.customer_acceptance is None
    assert current.snapshot == order.snapshot and current.authorization == order.authorization
    with client_for(service) as client:
        response = client.get(f"/runs/{order.snapshot.quote.request_id}/events")
        assert response.status_code == 200
        assert response.json()["payment"] == baseline["payment"]
        assert not any(e["type"] == "payment_captured" for e in response.json()["events"])
