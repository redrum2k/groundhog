"""Executable customer/worker harness. Fixture generation is outside the runtime package."""

import argparse
import base64
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.contracts.catalog import (
    AcceptQuoteCommand,
    ClarifyCommand,
    RequestCommand,
    RevisionCommand,
    UploadCommand,
)
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus.generate import seed  # noqa: E402


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 23, 19, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def run(scenario, output):
    summary_path = output / "summary.json"
    if summary_path.exists():
        saved = json.loads(summary_path.read_text())
        if saved["scenario"] != scenario:
            raise ValueError("output already belongs to another scenario; choose a fresh directory")
        return saved
    output.mkdir(parents=True, exist_ok=True)
    clock = Clock()
    service = CatalogService(
        CatalogRepository(output / "orders.sqlite3"), output / "evidence", clock,
        auto_mock_funding=True,
    )
    fixtures = seed(service)
    draft = service.create_request(
        RequestCommand(
            prompt="Find storage products under 2 kg and unit price no more than USD 40.",
            corpus_id="storage-2026",
            idempotency_key="request",
        )
    )
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile-1"),
    )
    if draft.question is None:
        raise RuntimeError("journey expected material weight-concept clarification")
    draft = service.clarify(
        draft.request_id,
        ClarifyCommand(
            expected_revision=draft.revision,
            idempotency_key="answer",
            question_id=draft.question.question_id,
            text="Use net unit weight.",
        ),
    )
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile-2"),
    )
    quote = service.issue_quote(
        draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="quote")
    )
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="customer:demo", idempotency_key="accept"
        )
    )
    order_id = order.snapshot.order_id
    order = service.run_one(order_id)
    if order.order_state != "waiting_evidence" or order.deliveries:
        raise RuntimeError(
            f"expected pre-delivery evidence repair, got {order.order_state}: {order.error}"
        )
    target = (
        fixtures["repair"]
        if scenario == "repaired"
        else fixtures["date_conflict"]
        if scenario == "date-conflict"
        else None
    )
    artifact = target.artifact if target else fixtures["unregistered"]
    order = service.upload(
        order_id,
        UploadCommand(
            expected_revision=order.revision,
            expected_binding=order.binding,
            idempotency_key="upload",
            evidence_request_id=order.evidence_requests[-1].request_id,
            actor="customer:demo",
            reason="Readable copy of the requested catalog pages.",
            relationship="replacement_page",
            pdf_base64=base64.b64encode(service.store.read(artifact)).decode(),
        ),
    )
    order = service.run_one(order_id)
    if scenario == "repaired":
        order = service.run_one(order_id)
        if order.order_state != "delivered":
            raise RuntimeError(f"repair failed: {order.order_state}: {order.error}")
        clock.advance(60)
    else:
        clock.advance(120)
    service.expire_due()
    order = service.get(order_id)
    view = service.view(order)
    (output / "order.json").write_text(view.model_dump_json(indent=2))
    (output / "human-review.json").write_text(
        json.dumps([row.model_dump(mode="json") for row in view.human_review], indent=2)
    )
    if order.deliveries:
        (output / "shortlist.pdf").write_bytes(service.store.read(order.deliveries[-1].pdf))
    summary = {
        "scenario": scenario,
        "order_id": order_id,
        "state": order.order_state,
        "mock_bookings": [b.kind for b in order.ledger],
        "review_rows": len(view.human_review),
        "output": str(output.resolve()),
        "synthetic_data": True,
        "model": "offline deterministic substitute",
    }
    expected = "closed" if scenario == "repaired" else "human_review"
    if order.order_state != expected:
        raise RuntimeError(f"expected {expected}, got {order.order_state}")
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run a fully offline catalog lifecycle with real PDF parsing.",
        epilog=(
            "Examples:\n  uv run --locked --directory backend python ../tools/offline_journey.py "
            "--scenario repaired --output artifacts/repaired\n"
            "  uv run --locked --directory backend python ../tools/offline_journey.py "
            "--scenario unresolved --output artifacts/unresolved"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario", choices=("repaired", "unresolved", "date-conflict"), required=True
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Fresh output directory; completed exact repeats return the saved result.",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.scenario, args.output), indent=2))
    except (ValueError, RuntimeError) as exc:
        parser.exit(
            1,
            f"Error: {exc}\nChoose a fresh --output directory and inspect order.json if present.\n",
        )


if __name__ == "__main__":
    main()
