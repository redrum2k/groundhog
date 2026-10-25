from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.contracts.catalog import AcceptQuoteCommand
from app.contracts.runs import RunOffer
from app.money import format_money, major_units
from app.orders.run_events import binding
from app.orders.runs import Runs
from tests.dataset.conftest import command, delivered, fund


@pytest.mark.parametrize(
    "minor,text",
    [
        (0, "0.00"),
        (1, "0.01"),
        (25, "0.25"),
        (50, "0.50"),
        (100, "1.00"),
        (101, "1.01"),
        (12000, "120.00"),
    ],
)
def test_exact_money_formatting(minor, text):
    assert format_money(SimpleNamespace(amount_minor=minor, decimals=2)) == text
    assert major_units(minor) * 100 == minor


@pytest.mark.parametrize("scope,minor", [("oakland", 50), ("yoga", 25)])
def test_canvas_quote_funding_and_booking_preserve_cents(dataset_service, scope, minor):
    service, _ = dataset_service
    parent = delivered(service)
    quote = Runs(service).offer(
        parent.snapshot.quote.request_id,
        RunOffer(binding=binding(parent), scope=scope),
        "offer",
        "provider:test",
    )
    child = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="buyer:test", idempotency_key="child"
        )
    )
    child = fund(service, child)
    child = service.run_one(child.snapshot.order_id)
    child = service.mutate(child.snapshot.order_id, "accept", command(child, "accept-delivery"))
    page = Runs(service).page(quote.request_id)
    contracts = [e.contract for e in page.events if e.type == "contract_approved"]
    amendments = [e.amendment for e in page.events if e.type == "amendment_signed"]
    payments = [
        e.payment for e in page.events if e.type in {"payment_authorized", "payment_state_changed"}
    ]
    assert contracts and amendments and payments
    assert all(Decimal(str(c.price)) * 100 == minor for c in contracts + amendments)
    assert all(Decimal(str(p.amount)) * 100 == minor for p in payments)
    assert any(
        f"Price ${minor // 100}.{minor % 100:02d}" in e.message.text
        for e in page.events
        if e.type == "message"
    )
    assert child.snapshot.quote.payment_terms.amount_atomic == minor * 10000
    assert child.ledger and child.ledger[-1].amount.amount_minor == minor
