import json

import pytest

from app.contracts.catalog import FulfillmentContext
from app.contracts.dataset import DatasetManifest, DatasetSpecification
from app.datasets import canonical, make_terms, parse_csv, verify_dataset
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.runtime.catalog_policy import capture_allowed
from tests.dataset.conftest import accepted, command, delivered, fund


def context(order):
    return FulfillmentContext(snapshot=order.snapshot, binding=order.binding, sources=order.sources)


def test_complete_bytes_funding_and_event_journey(dataset_service):
    service, clock = dataset_service
    order = accepted(service)
    assert isinstance(order.snapshot.quote.specification.terms, DatasetSpecification)
    assert order.snapshot.quote.policy.version == "aggregate-brokerage-v1"
    assert order.snapshot.quote.policy.pricing_version == "datumco-demo-pricing-v2"
    assert order.snapshot.quote.amount.amount_minor == 100
    assert order.snapshot.quote.payment_terms.amount_atomic == 1000000
    with pytest.raises(DomainError):
        service.claim_job(order.snapshot.order_id)
    order = fund(service, order)
    order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "delivered", order.error
    delivery = order.deliveries[-1]
    rows = parse_csv(service.store.read(delivery.csv))
    preview = DatasetManifest.model_validate_json(service.store.read(delivery.preview))
    assert rows == preview.rows
    assert set(r.zip for r in rows) == set(
        order.snapshot.quote.specification.terms.coverage.expected_keys
    )
    assert next(r for r in rows if r.zip == "94129").count is None
    assert (delivery.review_deadline - delivery.published_at).total_seconds() == 60
    assert not capture_allowed(order, clock())
    page = Runs(service).page(order.snapshot.quote.request_id)
    assert page.events and page.caught_up
    assert page.binding.evidenceVersion == 1 and page.binding.deliveryVersion == 1
    assert any(e.type == "payment_authorized" and e.payment.mock for e in page.events)
    assert not any(e.type == "payment_captured" for e in page.events)
    clock.advance(60)
    service.expire_due()
    service.expire_due()
    final = service.get(order.snapshot.order_id)
    assert len(final.ledger) == 1 and final.order_state == "closed"
    assert final.ledger[0].amount.amount_minor == 100
    page = Runs(service).page(order.snapshot.quote.request_id)
    captures = [e for e in page.events if e.type == "payment_captured"]
    assert len(captures) == 1 and captures[0].captureTx is None
    assert all(
        e.entries == [] and e.margin is None for e in page.events if e.type == "books_posted"
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "count", "geography", "preview", "suppressed", "schema"]
)
def test_independent_delivered_byte_validation(dataset_service, mutation):
    service, _ = dataset_service
    order = delivered(service)
    delivery = order.deliveries[-1]
    raw = service.store.read(delivery.csv)
    lines = raw.decode().splitlines()
    preview = delivery.preview
    if mutation == "missing":
        lines = [line for line in lines if not line.startswith("94110,")]
    elif mutation == "duplicate":
        lines.append(lines[1])
    elif mutation == "count":
        lines[1] = lines[1].replace(",100,", ",999,")
    elif mutation == "geography":
        lines[1] = lines[1].replace("94102", "94601")
    elif mutation == "suppressed":
        lines = [line.replace(",,suppressed", ",42,suppressed") for line in lines]
    elif mutation == "schema":
        lines[0] = "zip,area,people,status"
    elif mutation == "preview":
        data = json.loads(service.store.read(preview))
        data["rows"][0]["count"] = 999
        preview = service.store.put(canonical(data), "application/json")
    artifact = service.store.put(("\n".join(lines) + "\n").encode(), "text/csv")
    report, _ = verify_dataset(
        context(order),
        service.store,
        service.clock(),
        delivery=artifact,
        preview=preview,
        stage="delivery",
    )
    assert not report.passed and report.provider_defect
    assert all(ref.value != "42" for a in report.assessments for ref in a.citations)
    if mutation == "missing":
        ref = next(r for a in report.assessments for r in a.citations if r.expected_key == "94110")
        assert service.store.resolve(ref, (*order.artifacts, artifact)) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_min", 24),
        ("age_max", 35),
        ("geography", "Oakland"),
        ("category", "wellness"),
        ("count_unit", "households"),
        ("groups_disjoint", False),
        ("missing", None),
        ("duplicate", None),
        ("authority", None),
    ],
)
def test_bad_registered_source_is_not_provider_fault(dataset_service, field, value):
    service, _ = dataset_service
    order = accepted(service)
    sources = list(order.sources)
    index = next(i for i, s in enumerate(sources) if s.source_id.endswith(":gym_or_fitness_app"))
    source = sources[index]
    data = json.loads(service.store.read(source.artifact))
    if field == "missing":
        data["rows"] = [r for r in data["rows"] if r["zip"] != "94110"]
    elif field == "duplicate":
        data["rows"].append(data["rows"][0])
    elif field != "authority":
        data[field] = value
    artifact = service.store.put(canonical(data), "application/json")
    sources[index] = source.model_copy(
        update={
            "artifact": artifact,
            **(
                {"authority": "unverified", "authority_record": None}
                if field == "authority"
                else {}
            ),
        }
    )
    terms = make_terms(tuple(sources), service.store)
    spec = order.snapshot.quote.specification.model_copy(update={"terms": terms})
    quote = order.snapshot.quote.model_copy(
        update={"sources": tuple(sources), "specification": spec}
    )
    changed = order.model_copy(
        update={
            "sources": tuple(sources),
            "snapshot": order.snapshot.model_copy(update={"quote": quote}),
        }
    )
    report, _ = verify_dataset(context(changed), service.store, service.clock())
    assert not report.passed and not report.provider_defect
    assert changed.free_corrections_used == 0


def test_all_mandatory_registry_and_actual_bytes_required_at_capture(dataset_service):
    service, clock = dataset_service
    order = delivered(service)
    clock.advance(60)
    assert capture_allowed(order, clock())
    empty = order.verification.model_copy(update={"obligations": (), "assessments": ()})
    assert not capture_allowed(order.model_copy(update={"verification": empty}), clock())
    report = order.verification.model_copy(
        update={
            "obligations": order.verification.obligations[:-1],
            "assessments": order.verification.assessments[:-1],
        }
    )
    assert not capture_allowed(order.model_copy(update={"verification": report}), clock())
    path = service.store.root / order.deliveries[-1].csv.storage_key
    path.write_bytes(b"tampered")
    assert not service.current_dataset_checks(order)
    with pytest.raises(DomainError):
        service.mutate(order.snapshot.order_id, "accept", command(order, "accept"), advance=False)
    assert service.get(order.snapshot.order_id).ledger == ()


def test_new_happy_path_never_calls_pdf_tools(dataset_service, monkeypatch):
    service, _ = dataset_service
    monkeypatch.setattr("app.catalog.artifacts.layout", lambda *a: pytest.fail("PDF path used"))
    assert delivered(service).order_state == "delivered"
