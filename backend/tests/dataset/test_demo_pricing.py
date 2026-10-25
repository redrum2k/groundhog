import pytest

from app.contracts.catalog import CatalogOrder, QuoteRequest
from app.contracts.runs import RunOffer
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.storage.catalog import CatalogRepository
from tests.dataset.conftest import accepted, delivered


@pytest.mark.parametrize(
    "scope,minor,atomic",
    [("oakland", 50, 500000), ("yoga", 25, 250000), ("replacement", 100, 1000000)],
)
def test_new_offers_freeze_lower_price_and_exact_escrow_amount(
    dataset_service, scope, minor, atomic
):
    service, _ = dataset_service
    order = delivered(service)
    quote = Runs(service).offer(
        order.snapshot.quote.request_id,
        RunOffer(binding=binding(order), scope=scope),
        "demo-offer",
        "provider:test",
    )
    assert quote.policy.pricing_version == "datumco-demo-pricing-v2"
    assert quote.amount.amount_minor == minor
    assert quote.payment_terms.display_amount == quote.amount
    assert quote.payment_terms.amount_atomic == atomic
    assert quote.payment_terms.payment_info.max_amount == atomic


def test_existing_prices_and_replays_survive_new_pricing(dataset_service, monkeypatch):
    service, clock = dataset_service
    with monkeypatch.context() as old:
        old.setattr("app.orders.catalog.DATASET_PRICING", "datumco-demo-pricing-v1")
        old.setattr("app.orders.catalog.DATASET_PRICES_MINOR", {"initial": 12000})
        original = accepted(service, key="old-price")
    quote = original.snapshot.quote
    current = accepted(service, key="new-price")
    assert current.snapshot.quote.amount.amount_minor == 100
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    assert restarted.get(original.snapshot.order_id).snapshot == original.snapshot
    replay = restarted.issue_quote(
        quote.request_id,
        QuoteRequest(expected_revision=quote.request_revision, idempotency_key="quote:old-price"),
    )
    assert replay == quote
    assert replay.amount.amount_minor == 12000
    assert replay.payment_terms.amount_atomic == 120000000
    historical = original.model_dump(mode="json")
    del historical["snapshot"]["quote"]["policy"]["pricing_version"]
    assert (
        CatalogOrder.model_validate(historical).snapshot.quote.policy.pricing_version
        == "datumco-demo-pricing-v1"
    )
