import json
from decimal import Decimal

import pytest

from app.catalog.documents import extract_source, pdf_document, produce
from app.catalog.verification import material_blockers, verify
from app.contracts.catalog import Assessment, FulfillmentContext, Obligation, Provenance
from app.orders.service import DomainError

from .fixtures import accepted, repaired


def test_pdf_verifier_detects_actual_pdf_defect_even_with_correct_sidecar(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    delivery = order.deliveries[-1]
    sidecar = json.loads(service.store.read(delivery.sidecar))
    assert sidecar["delivery_sha256"] == delivery.pdf.sha256
    bad = service.store.put(
        pdf_document("Cited product shortlist", ["SELECT S01 | Wrong box | supplier-a"])
    )
    context = FulfillmentContext(
        snapshot=order.snapshot, binding=order.binding, sources=order.sources
    )
    result, _ = verify(context, service.store, clock(), delivery=bad, stage="delivery")
    assert result.provider_defect and not result.passed
    check = next(a for a in result.assessments if a.obligation_id == "global:pdf")
    assert check.result == "FAIL" and check.citations[0].artifact_id == bad.artifact_id


def test_sidecars_are_derived_from_artifacts_and_exact_spans_resolve(setup):
    service, _, fixtures = setup
    source = extract_source(fixtures["sources"][1], service.store)
    assert any(p.unit_price is None for p in source.products)
    for product in source.products:
        for citation in product.citations:
            assert service.store.resolve(citation, (source.source.artifact,)) == citation.quote
    citation = source.products[0].citations[0]
    with pytest.raises(ValueError, match="span"):
        service.store.resolve(
            citation.model_copy(update={"quote": "invented source"}), (source.source.artifact,)
        )
    with pytest.raises(ValueError, match="outside"):
        service.store.resolve(citation, ())


def test_unknown_price_on_weight_excluded_product_does_not_block(setup):
    service, clock, _ = setup
    order = accepted(service)
    context = FulfillmentContext(
        snapshot=order.snapshot, binding=order.binding, sources=order.sources
    )
    report, _ = verify(context, service.store, clock())
    # S18 has net weight 2 kg; the strict < 2 kg filter excludes it independently of price.
    irrelevant = next(a for a in report.assessments if a.obligation_id == "supplier-b/S18:price")
    assert (
        irrelevant.result == "UNKNOWN" and irrelevant.obligation_id not in report.material_blockers
    )
    assert "supplier-b/S17:price" in report.material_blockers


def test_materiality_is_dependency_based_and_ignores_decorative_uncertainty():
    provenance = Provenance(kind="deterministic", assessor="test", version="1")
    checks = (
        Obligation(
            obligation_id="footer",
            requirement_id="R-PDF",
            subject="footer",
            field="decoration",
            check="read",
            mandatory=False,
            decision_effect="none",
        ),
    )
    results = (
        Assessment(
            obligation_id="footer",
            result="UNKNOWN",
            missing_facts=("Unreadable flourish",),
            reason_code="REQUIRED_VALUE_UNREADABLE",
            explanation="Decorative only",
            provenance=provenance,
        ),
    )
    assert material_blockers(checks, results) == ()
    blocking = checks[0].model_copy(update={"mandatory": True, "decision_effect": "compliance"})
    assert material_blockers((blocking,), results) == ("footer",)


def test_one_durable_free_correction_then_escalation(setup, monkeypatch):
    service, _, fixtures = setup
    # Select the readable registered edition before accepting the order.
    readable = fixtures["repair"].model_copy(update={"version": 6})
    service.registry.register(readable)
    order = accepted(service)
    original_produce = produce

    def defective(extracted, terms, store):
        _, sidecar = original_produce(extracted, terms, store)
        return store.put(
            pdf_document("Cited product shortlist", ["SELECT S01 | incorrect | supplier-a"])
        ), sidecar

    monkeypatch.setattr("app.orders.catalog.produce", defective)
    order = service.run_one(order.snapshot.order_id)
    assert order.free_corrections_used == 1 and order.order_state == "processing"
    assert len([j for j in order.jobs if j.kind == "correct"]) == 1
    assert not order.deliveries
    order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.ledger
    assert order.free_corrections_used == 1


def test_free_correction_operational_failure_escalates(setup, monkeypatch):
    service, _, fixtures = setup
    service.registry.register(fixtures["repair"].model_copy(update={"version": 6}))
    order = accepted(service)
    with service.repository.transaction() as db:
        service._reserve_correction(order)
        service._save(db, order)

    def fail(*args, **kwargs):
        raise RuntimeError("renderer offline")

    monkeypatch.setattr("app.orders.catalog.produce", fail)
    order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "human_review" and order.delivery_state == "operational_failure"
    assert not order.deliveries and not order.ledger


def test_hash_integrity_and_storage_escape(setup):
    service, _, fixtures = setup
    artifact = fixtures["sources"][0].artifact
    with pytest.raises(DomainError, match="unavailable"):
        service.store.read(artifact.model_copy(update={"storage_key": "../secret.pdf"}))
    with pytest.raises(DomainError, match="hash"):
        service.store.read(artifact.model_copy(update={"sha256": "0" * 64}))
    with pytest.raises(ValueError, match="PDF"):
        service.store.put(b"not pdf")


def test_units_are_normalized_before_exact_comparison(setup):
    from app.catalog.documents import disposition

    service, _, fixtures = setup
    order = accepted(service)
    product = extract_source(fixtures["sources"][0], service.store).products[0]
    assert product.net_kg == Decimal("1.00")
    terms = order.snapshot.quote.specification.terms.model_copy(
        update={"weight_unit": "g", "weight_threshold": Decimal("1000"), "weight_operator": "lte"}
    )
    assert disposition(product, terms)[0] == "included"
    terms = terms.model_copy(update={"weight_operator": "lt"})
    assert disposition(product, terms) == ("excluded", "weight")


def test_supported_post_delivery_defect_publishes_one_corrected_version(setup):
    from app.contracts.catalog import Complaint, DisputeCommand

    from .fixtures import cmd

    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    original = order.deliveries[0]
    # Simulate a historical producer defect discovered by a later independent check.
    broken = service.store.put(
        pdf_document("Cited product shortlist", ["SELECT S01 | incorrect | supplier-a"])
    )
    order.deliveries = (original.model_copy(update={"pdf": broken}),)
    order.artifacts = (*order.artifacts, broken)
    with service.repository.transaction() as db:
        service._save(db, order)
    order = service.mutate(
        order.snapshot.order_id,
        "dispute",
        cmd(
            order,
            "dispute",
            DisputeCommand,
            complaint=Complaint(
                text="Incorrect product content",
                product_id="S01",
                field="pdf",
                requirement_id="R-PDF",
                artifact_id=broken.artifact_id,
            ),
        ),
    )
    order = service.run_one(order.snapshot.order_id)
    assert order.cases[-1].status == "supported" and order.free_corrections_used == 1
    order = service.run_one(order.snapshot.order_id)
    assert len(order.deliveries) == 2 and order.deliveries[-1].version == 2
    assert order.verification.passed and not order.ledger
    assert "dispute" in service.view(order).available_actions
    clock.advance(60)
    assert len(service.get(order.snapshot.order_id).ledger) == 1


def test_runtime_package_and_contracts_exclude_evaluation_truth():
    import ast
    from pathlib import Path

    from pydantic import ValidationError

    from app.contracts.catalog import RequestCommand

    root = Path(__file__).resolve().parents[2] / "app"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("evals", "tools.corpus", "corpus.generate")
                )
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(("evals", "tools.corpus", "corpus.generate"))
                    for alias in node.names
                )
    with pytest.raises(ValidationError):
        RequestCommand(
            prompt="storage", corpus_id="x", idempotency_key="k", expected_verdict="PASS"
        )


def test_unusable_repair_is_unknown_evidence_not_engine_failure(setup):
    from .fixtures import upload

    service, _, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    unrelated = service.store.put(
        pdf_document("Supplier attachment", ["No readable catalog identity or product values."])
    )
    order = upload(service, order, unrelated)
    order = service.run_one(order.snapshot.order_id)
    assert order.amendments[-1].classification == "unresolved"
    assert order.amendments[-1].assessment[0].result == "UNKNOWN"
    assert order.order_state == "waiting_evidence" and order.delivery_state != "operational_failure"


def test_malformed_pdf_is_rejected_as_input(setup):
    service, _, _ = setup
    with pytest.raises(ValueError, match="malformed"):
        service.store.put(b"%PDF-1.4 invalid file")
