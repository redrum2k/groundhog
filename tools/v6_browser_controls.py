"""Persist explicit synthetic negative controls through actual catalog lifecycle/storage.

No desired-verdict HTTP parameter or model-generated negative candidate is fabricated.
"""
import argparse
import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.catalog.documents import pdf_document, produce
from app.contracts.catalog import AcceptQuoteCommand, RequestCommand, RevisionCommand, Source
from app.contracts.catalog_improvement import CatalogPatchProposal
from app.contracts.payments import FundingAuthorization
from app.improvement.catalog import CatalogProcedures
from app.improvement.catalog_probe import command
from app.orders.catalog import CatalogService
from app.orders.service import utc_now
from app.storage.catalog import CatalogRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-preaccept", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=args.resume_preaccept)
    if (args.output / "setup.json").exists():
        raise SystemExit("Completed fixture already exists; never rerun its output failure")
    service = CatalogService(CatalogRepository(args.database), args.artifacts, utc_now)
    procedures = CatalogProcedures(service)
    invalid = {"corpus_id": "storage-2026", "baseline_version": "catalog-static-v1", "incident_ids": ["injected-control"],
               "rationale": "Injected protected-change rejection control, not an application-model proposal",
               "expected_mechanism": "Attempt a forbidden capture operation; it must be rejected before execution",
               "operations": [{"op": "capture", "trigger": "REQUIRED_VALUE_UNREADABLE"}]}
    try:
        CatalogPatchProposal.model_validate(invalid)
        raise RuntimeError("Protected control unexpectedly validated")
    except ValidationError as error:
        previous = [r.data for r in procedures.view("storage-2026").records
                    if r.kind == "catalog_rejection_control" and r.data.get("requested") == invalid]
        if previous:
            rejection = previous[0]
        else:
            with procedures.store.connect(write=True) as db:
                rejection = procedures._put(db, "rejection_control", "storage-2026", {
                "mode": "INJECTED_SCHEMA_NEGATIVE_CONTROL", "requested": invalid,
                "status": "REJECTED_BEFORE_EXECUTION",
                "errors": [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in error.errors()],
            }, actor="test:synthetic-protected-control")
    raw = pdf_document("Supplier catalog", [
        "Supplier: supplier-correction-v6 / Edition: 2026-C / Effective: 2026-10-01",
        "Records: S601, S602, S603", "S601 | storage | Correction box one",
        "net=1.125 kg | shipping=1.900 kg | unit=USD 18.65",
        "S602 | storage | Correction box two", "net=1.875 kg | shipping=2.300 kg | unit=USD 38.95",
        "S603 | storage | Large correction box", "net=2.250 kg | shipping=2.900 kg | unit=USD 10.20",
    ])
    source = Source(source_id="supplier-correction-v6", version=1, corpus_id="v6-correction-demo",
                    supplier_id="supplier-correction-v6", edition="2026-C", effective_date=date(2026, 10, 1),
                    authority="registered_supplier_publication", authority_record="synthetic-registry:browser-correction",
                    artifact=service.store.put(raw))
    service.registry.register(source)
    draft = service.create_request(RequestCommand(prompt="Select storage products with net unit weight below 2 kg and unit price at most USD 40.",
                                                   corpus_id=source.corpus_id, idempotency_key="v6-browser-fail-draft"))
    if service.get_request(draft.request_id).order_id is not None:
        raise SystemExit("Order already accepted; inspect exact phase before any recovery")
    draft = service.compile_request(draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"))
    quote = service.issue_quote(draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="quote"))
    order = service.accept_quote(AcceptQuoteCommand(quote_id=quote.quote_id, customer_actor="customer:synthetic-browser-control", idempotency_key="v6-browser-fail-accept"))
    prep = service.payments.prepare(order.snapshot.order_id, command(order, "prepare"))
    order = service.payments.authorize(order.snapshot.order_id, command(order, "fund", FundingAuthorization,
        funding_attempt_id=prep.funding_attempt_id, payment_hash=prep.terms.payment_hash, simulate=True))
    service.payments.work()
    order = service.get(order.snapshot.order_id)
    def faulty_producer(extracted, terms, store):
        _, sidecar = produce(extracted, terms, store)
        # An actual wrong value in actual delivered bytes; sidecar does not decide verification.
        lines = ["SELECT S601 | Correction box one | supplier-correction-v6",
                 "net_unit=1.125 kg | unit=USD 18.56", f"source=supplier-correction-v6@1 p1 sha={source.artifact.sha256[:12]}",
                 "SELECT S602 | Correction box two | supplier-correction-v6",
                 "net_unit=1.875 kg | unit=USD 38.95", f"source=supplier-correction-v6@1 p1 sha={source.artifact.sha256[:12]}",
                 "EXCLUDED S603 | weight"]
        return store.put(pdf_document("Cited product shortlist", lines)), sidecar
    service.producer = faulty_producer
    order = service.run_one(order.snapshot.order_id)
    assert order.free_corrections_used == 1 and not order.ledger and not order.deliveries
    assert any(v.provider_defect for v in order.verification_history)
    assert any(j.kind == "correct" and j.status == "queued" for j in order.jobs)
    report = {"mode": "deterministic fixture setup / injected producer bytes / actual verification / mock funding",
              "order_id": order.snapshot.order_id, "rejection_control": rejection,
              "order": service.view(order).model_dump(mode="json")}
    (args.output / "setup.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"order_id": order.snapshot.order_id, "state": order.order_state,
                      "provider_defect_retained": True, "free_correction_queued": True, "model_calls": 0}))


if __name__ == "__main__":
    main()
