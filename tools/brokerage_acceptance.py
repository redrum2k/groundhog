"""Run synthetic brokerage acceptance locally without sockets, paid models or RPC."""

import argparse
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.contracts.catalog import (
    AcceptQuoteCommand,
    ClarifyCommand,
    Complaint,
    DisputeCommand,
    OrderCommand,
    QuoteRequest,
    RevisionCommand,
)
from app.contracts.payments import FundingAuthorization
from app.contracts.runs import RunCreate, RunOffer
from app.datasets import produce_dataset
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.storage.catalog import CatalogRepository


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 24, 12, tzinfo=UTC)

    def __call__(self):
        return self.now


def cmd(order, key):
    return OrderCommand(
        expected_revision=order.revision, expected_binding=order.binding, idempotency_key=key
    )


def accept(service, quote, key):
    return service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id,
            customer_actor="AcmeFitness:offline-harness",
            idempotency_key=key,
        )
    )


def new_order(service, key):
    run = Runs(service).create(RunCreate(), key)
    draft = service.get_request(run.id)
    draft = service.compile_request(
        run.id, RevisionCommand(expected_revision=draft.revision, idempotency_key=key + ":compile")
    )
    assert draft.question
    draft = service.clarify(
        run.id,
        ClarifyCommand(
            expected_revision=draft.revision,
            question_id=draft.question.question_id,
            text="Gym membership or fitness-app use.",
            idempotency_key=key + ":answer",
        ),
    )
    draft = service.compile_request(
        run.id, RevisionCommand(expected_revision=draft.revision, idempotency_key=key + ":compile2")
    )
    quote = service.issue_quote(
        run.id, QuoteRequest(expected_revision=draft.revision, idempotency_key=key + ":quote")
    )
    return accept(service, quote, key + ":accept")


def fund(service, order):
    preparation = service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
    order = service.payments.authorize(
        order.snapshot.order_id,
        FundingAuthorization(
            **cmd(order, "authorize").model_dump(),
            funding_attempt_id=preparation.funding_attempt_id,
            payment_hash=preparation.terms.payment_hash,
            simulate=True,
        ),
    )
    assert not order.deliveries
    service.payments.work()
    return service.run_one(order.snapshot.order_id)


def save(service, order, output, name):
    page = Runs(service).page(order.snapshot.quote.request_id)
    (output / f"{name}-events.json").write_text(page.model_dump_json(indent=2, by_alias=True))
    (output / f"{name}-order.json").write_text(
        service.current_view(order.snapshot.order_id).model_dump_json(indent=2)
    )
    for delivery in order.deliveries:
        (output / f"{name}-v{delivery.version}.csv").write_bytes(service.store.read(delivery.csv))
    return {
        "run_id": page.request.request_id,
        "order_id": order.snapshot.order_id,
        "state": order.order_state,
        "delivery_versions": len(order.deliveries),
        "free_corrections": order.free_corrections_used,
        "bookings": [b.model_dump(mode="json") for b in order.ledger],
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run --locked --directory backend python "
            "../tools/brokerage_acceptance.py --output /private/tmp/datumco-acceptance"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Parent for a fresh evidence directory; existing files are preserved.",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="broker-", dir=args.output))
    clock = Clock()
    service = CatalogService(
        CatalogRepository(output / "orders.sqlite3"), output / "artifacts", clock
    )
    base = fund(service, new_order(service, "conforming"))
    assert base.verification.passed and len(base.deliveries) == 1 and not base.ledger
    clock.now += timedelta(seconds=60)
    base = service.get(base.snapshot.order_id)
    assert len(base.ledger) == 1 and base.ledger[0].receipt.transaction_id is None
    results = {"conforming": save(service, base, output, "conforming")}
    calls = []

    def missing_zip(terms, sources, store):
        csv, preview = produce_dataset(terms, sources, store)
        calls.append(1)
        if len(calls) == 1:
            raw = (
                b"\n".join(
                    line for line in store.read(csv).splitlines() if not line.startswith(b"94110,")
                )
                + b"\n"
            )
            csv = store.put(raw, "text/csv")
        return csv, preview

    with patch("app.orders.dataset.produce_dataset", missing_zip):
        correction = fund(service, new_order(service, "explicit-output-fault"))
        assert correction.free_corrections_used == 1 and not correction.deliveries
        correction = service.run_one(correction.snapshot.order_id)
    assert correction.verification.passed
    results["explicit_missing_zip_fault"] = save(service, correction, output, "correction")
    parent = fund(service, new_order(service, "expansion"))
    offer = Runs(service).offer(
        parent.snapshot.quote.request_id,
        RunOffer(binding=binding(parent), scope="oakland"),
        "oakland",
        "provider:offline-harness",
    )
    child = accept(service, offer, "accept-oakland")
    assert not child.authorization.receipt and not child.deliveries
    child = fund(service, child)
    assert child.snapshot.quote.amount.amount_minor == 6000 and child.verification.passed
    results["oakland"] = save(service, child, output, "oakland")
    yoga = fund(service, new_order(service, "yoga"))
    yoga = service.mutate(
        yoga.snapshot.order_id,
        "dispute",
        DisputeCommand(
            **cmd(yoga, "yoga-dispute").model_dump(),
            complaint=Complaint(
                artifact_id=yoga.deliveries[-1].csv.artifact_id,
                requirement_id="R-CATEGORY",
                product_id="dataset",
                field="category",
                text="Does standalone yoga count?",
                intent="dispute_fact",
            ),
        ),
    )
    yoga = service.run_one(yoga.snapshot.order_id)
    assert (
        yoga.cases[-1].status == "unsupported"
        and not yoga.free_corrections_used
        and not yoga.ledger
    )
    results["yoga"] = save(service, yoga, output, "yoga")
    report = {
        "mode": "offline mock; missing-ZIP output fault is explicitly injected",
        "output": str(output),
        "cases": results,
        "live_rpc": False,
        "browser_executed": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
