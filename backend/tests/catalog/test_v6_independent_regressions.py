"""Independent-review reproductions: source facts, not generator-side verdicts."""

from collections import Counter

from app.catalog.acquisition import acquire_registered, registered_repair
from app.catalog.documents import extract_source, output_lines, pdf_document
from app.catalog.verification import verify
from app.contracts.catalog import FulfillmentContext
from app.improvement.catalog_probe import (
    VisibleCatalogCase,
    catalog_page,
    development_cases,
    publication,
    run_visible_case,
)
from tests.catalog.fixtures import accepted, repaired, upload


def test_swapped_values_and_citations_fail_but_whole_record_reordering_passes(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    context = FulfillmentContext(
        snapshot=order.snapshot, binding=order.binding, sources=order.sources
    )
    expected = output_lines(
        tuple(extract_source(s, service.store) for s in order.sources),
        order.snapshot.quote.specification.terms,
    )
    starts = [i for i, line in enumerate(expected) if line.startswith("SELECT ")]
    first = starts[0]
    second = next(i for i in starts[1:] if expected[i + 1] != expected[first + 1])
    for offset in (1, 2):
        other = (
            second
            if offset == 1
            else next(i for i in starts[1:] if expected[i + 2] != expected[first + 2])
        )
        swapped = list(expected)
        swapped[first + offset], swapped[other + offset] = (
            swapped[other + offset],
            swapped[first + offset],
        )
        assert Counter(swapped) == Counter(expected)  # Previous verifier's entire test.
        pdf = service.store.put(pdf_document("Cited product shortlist", swapped))
        report, _ = verify(context, service.store, clock(), delivery=pdf)
        assert report.provider_defect and not report.passed
    reordered = list(expected)
    reordered[first : first + 3], reordered[second : second + 3] = (
        expected[second : second + 3],
        expected[first : first + 3],
    )
    pdf = service.store.put(pdf_document("Cited product shortlist", reordered))
    report, _ = verify(context, service.store, clock(), delivery=pdf)
    assert report.passed


def test_precision_is_preserved_in_actual_delivered_pdf(setup):
    service, clock, fixtures = setup
    source = fixtures["sources"][0].model_copy(
        update={
            "artifact": service.store.put(
                pdf_document(
                    "Supplier catalog",
                    [
                        "Supplier: supplier-a / Edition: 2026-A / Effective: 2026-10-01",
                        "Records: S901",
                        "S901 | storage | Precise box",
                        "net=1.9999 kg | shipping=2.1000 kg | unit=USD 39.999",
                    ],
                )
            )
        }
    )
    order = accepted(service)
    terms = order.snapshot.quote.specification.terms
    from app.catalog.documents import produce

    pdf, _ = produce((extract_source(source, service.store),), terms, service.store)
    text = "\n".join(service.store.pages(pdf))
    assert "net_unit=1.9999 kg | unit=USD 39.999" in text
    context = FulfillmentContext(snapshot=order.snapshot, binding=order.binding, sources=(source,))
    report, _ = verify(context, service.store, clock(), delivery=pdf)
    assert report.passed
    rounded = service.store.put(
        pdf_document(
            "Cited product shortlist",
            [
                "SELECT S901 | Precise box | supplier-a",
                "net_unit=2.000 kg | unit=USD 40.00",
                f"source=supplier-a@1 p1 sha={source.artifact.sha256[:12]}",
            ],
        )
    )
    report, _ = verify(context, service.store, clock(), delivery=rounded)
    assert report.provider_defect and not report.passed


def test_conflicting_registered_repairs_never_win_by_version_or_upload_path(setup):
    service, _, fixtures = setup
    repair = fixtures["repair"]
    pages = service.store.pages(repair.artifact)
    lines = [line for text in pages for line in text.splitlines()]
    index = next(i for i, line in enumerate(lines) if line.startswith("S17 |"))
    lines[index + 1] = lines[index + 1].split("unit=USD ")[0] + "unit=USD 49.10"
    # Keep bounded catalog input only; renderer adds its own boilerplate.
    lines = [
        line for line in lines if line.startswith(("Supplier:", "Records:", "S1", "S2", "net="))
    ]
    conflict = repair.model_copy(
        update={
            "version": 9,
            "artifact": service.store.put(pdf_document("Supplier catalog", lines)),
        }
    )
    service.registry.register(conflict, selectable=False)
    order = service.run_one(accepted(service).snapshot.order_id)
    assert registered_repair(service, order) is None
    assert acquire_registered(service, order) == order
    # Directly uploading the earlier registered copy cannot bypass the conflict.
    order = upload(service, order, repair.artifact)
    order = service.run_one(order.snapshot.order_id)
    assessment = order.amendments[-1].assessment[0]
    assert assessment.result == "CONFLICT"
    assert assessment.reason_code == "REGISTERED_REPAIR_CONFLICT"
    assert not order.deliveries and not order.ledger


def test_probe_reports_archived_defect_and_completed_correction():
    case = development_cases("precision-test")[4]
    result = run_visible_case(case, arm="current_static")
    assert result["provider_defect_observed"] is True
    assert result["seller_rework_attempts"] == 1
    assert result["operationally_closed"] is True
    assert result["violations"] == []


def test_conflict_is_order_independent_in_all_recipe_arms():
    initial = publication(catalog_page())
    for first_price, second_price in (("29.10", "49.10"), ("49.10", "29.10")):
        case = VisibleCatalogCase(
            id="conflicting-repairs",
            corpus_id="conflict-test",
            prompt=(
                "Select storage products with net unit weight below 2 kg "
                "and unit price at most USD 40."
            ),
            publications=(
                initial,
                publication(catalog_page(price=first_price), 2, selectable=False),
                publication(catalog_page(price=second_price), 3, selectable=False),
            ),
        )
        for arm in ("current_static", "competent_static"):
            result = run_visible_case(case, arm=arm)
            assert result["financial_effects"] == []
            assert result["operationally_closed"] is False
