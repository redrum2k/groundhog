"""HTTP regressions for review R1; all evidence is synthetic and retained privately."""

import json

import pytest
from fastapi.testclient import TestClient

from app.contracts.catalog import FulfillmentContext
from app.contracts.runs import RunCreate
from app.datasets import canonical, reference, verify_dataset
from app.main import create_app
from app.orders.runs import Runs
from app.orders.service import DomainError
from tests.catalog.fixtures import accepted as catalog_accepted
from tests.dataset.conftest import accepted, delivered, fund


def client_for(service):
    return TestClient(
        create_app(
            service.repository.path,
            artifact_root=service.store.root,
            clock=service.clock,
            run_worker=False,
            payment_mode="mock",
        )
    )


@pytest.mark.parametrize("marker", ["missing", "renamed", "present"])
@pytest.mark.parametrize("status", ["suppressed", "unknown"])
def test_malformed_registered_source_withheld_at_every_public_boundary(
    dataset_service, marker, status
):
    service, _ = dataset_service
    Runs(service).create(RunCreate(), "seed")
    source = next(
        s
        for s in service.registry.manifest("sf-aggregate-v1")
        if s.source_id.endswith(":gym_or_fitness_app")
    )
    data = json.loads(service.store.read(source.artifact))
    data["version"] = 2
    row = next(r for r in data["rows"] if r["zip"] == "94129")
    row.update(count=42, status=status)
    if marker != "present":
        value = data.pop("count_unit")
        if marker == "renamed":
            data["units"] = value
    artifact = service.store.put(canonical(data), "application/json")
    service.registry.register(source.model_copy(update={"version": 2, "artifact": artifact}))
    order = accepted(service)
    report, _ = verify_dataset(
        FulfillmentContext(
            snapshot=order.snapshot,
            binding=order.binding,
            sources=order.sources,
        ),
        service.store,
        service.clock(),
    )
    assert not report.passed
    order = fund(service, order)
    order = service.run_one(order.snapshot.order_id)
    with client_for(service) as client:
        response = client.get(f"/orders/{order.snapshot.order_id}/artifacts/{artifact.artifact_id}")
        assert response.status_code == 409
        assert '"count":42' not in response.text
        page = client.get(f"/runs/{order.snapshot.quote.request_id}/events")
        assert page.status_code == 200
        assert '"count":42' not in page.text
    ref = reference(artifact, source.source_id, row="94129", column="count", value="42", version=2)
    with pytest.raises((DomainError, ValueError)):
        service.store.resolve(ref, order.artifacts)
    assert service.store.read(artifact) == canonical(data)


def test_allowed_source_coverage_authority_and_delivery_downloads(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    with client_for(service) as client:
        for artifact in order.artifacts:
            response = client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{artifact.artifact_id}"
            )
            assert response.status_code == 200
            assert response.content == service.store.read(artifact)
        source = next(s for s in order.sources if s.source_id.endswith(":authority"))
        ref = reference(source.artifact, source.source_id, column="yoga_category", value="Wellness")
        assert service.store.resolve(ref, order.artifacts) == "Wellness"
        page = client.get(f"/runs/{order.snapshot.quote.request_id}/events").json()
        evidence = next(e["evidence"] for e in page["events"] if e["type"] == "evidence_found")
        resolved = client.get(f"/runs/{order.snapshot.quote.request_id}/evidence/{evidence['id']}")
        assert resolved.status_code == 200
        assert resolved.json()["value"] == evidence["value"]


@pytest.mark.parametrize(
    "raw",
    [
        b'{"rows":[{"zip":"94129","count":42}]}',
        b"{}",
        b"[]",
        b'{"kind":"authority","count":42}',
        b"{",
    ],
)
def test_unknown_json_is_not_a_public_artifact(dataset_service, raw):
    service, _ = dataset_service
    order = accepted(service)
    artifact = service.store.put(raw, "application/json")
    with service.repository.transaction() as db:
        order.artifacts = (*order.artifacts, artifact)
        service._save(db, order)
    with client_for(service) as client:
        assert (
            client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{artifact.artifact_id}"
            ).status_code
            == 409
        )
    assert service.store.read(artifact) == raw


def test_historical_catalog_pdf_access_is_intact(setup):
    service, _, _ = setup
    order = catalog_accepted(service)
    with client_for(service) as client:
        for source in order.sources:
            response = client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{source.artifact.artifact_id}"
            )
            assert response.status_code == 200
            assert response.content == service.store.read(source.artifact)
            assert response.content.startswith(b"%PDF-")


def test_duplicate_json_keys_cannot_hide_an_unsafe_count(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    preview = order.deliveries[-1].preview
    raw = service.store.read(preview).replace(b'"count":null', b'"count":42,"count":null')
    assert raw != service.store.read(preview)
    artifact = service.store.put(raw, "application/json")
    with service.repository.transaction() as db:
        order.artifacts = (*order.artifacts, artifact)
        service._save(db, order)
    with client_for(service) as client:
        assert (
            client.get(
                f"/orders/{order.snapshot.order_id}/artifacts/{artifact.artifact_id}"
            ).status_code
            == 409
        )
    assert service.store.read(artifact) == raw
