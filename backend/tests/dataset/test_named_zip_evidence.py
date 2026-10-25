"""Capture actual model-bound input without calling or simulating an LLM answer."""

import json

import pytest

from app.investigation.dataset import investigate_dataset
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.conftest import delivered
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_review import wire


@pytest.mark.parametrize(
    "zip_key,field", [("94105", "artifact"), ("94129", "suppression"), ("94110", "suppression")]
)
def test_named_zip_count_and_status_reach_model_with_frozen_source(dataset_service, zip_key, field):
    service, _ = dataset_service
    text = (
        f"Examine the count and status for ZIP {zip_key}; do not assume a present row is correct."
    )
    ready = delivered(service)
    report = ready.verification
    assert report.passed
    order = dispute(service, ready, text=text, field=field, product=zip_key)
    packet = {}

    class Captured(Exception):
        pass

    class CaptureInput:
        def assess_obligation(self, obligation, claim, passages):
            packet.update(claim=claim, passages=passages)
            raise Captured()  # No provider request, predicted answer or persisted finding.

    with pytest.raises(Captured):
        investigate_dataset(order, report, service.store, CaptureInput())
    assert text in packet["claim"]
    source = next(
        s
        for s in order.sources
        if s.source_id.endswith(":" + order.snapshot.quote.specification.terms.category)
    )
    row = next(
        r for r in json.loads(service.store.read(source.artifact))["rows"] if r["zip"] == zip_key
    )
    refs = [p.citation for p in packet["passages"]]
    for source_id in ("delivery", source.source_id):
        for column in ("count", "status"):
            matching = [
                r
                for r in refs
                if r.source_id == source_id and r.row == zip_key and r.column == column
            ]
            assert len(matching) == 1, (source_id, zip_key, column)
            value = None if row[column] is None else str(row[column])
            assert matching[0].value == service.store.resolve(matching[0], order.artifacts) == value
    assert len(refs) <= 32
    assert not service.get(order.snapshot.order_id).ledger


def test_named_zip_cells_reach_both_blind_calls_without_first_answer(dataset_service, monkeypatch):
    service, _ = dataset_service
    text = "ZIP 94105 has a released aggregate count."
    order = dispute(service, delivered(service), text=text, field="artifact", product="94105")
    calls = wire(service, monkeypatch)  # Explicit synthetic transport, no provider traffic.
    assert CatalogWorker(service).run_once()
    assert len(calls) == 2
    first, second = calls[0][1], calls[1][1]
    assert second["complaint"] == text
    assert "FIRST_ANSWER_MUST_NOT_REACH_REVIEWER" not in json.dumps(second)
    for evidence in (first["evidence"], second["frozen_evidence_packet"]["passages"]):
        target = [p["citation"] for p in evidence if p["citation"]["row"] == "94105"]
        assert len(target) == 4
        assert {r["column"] for r in target} == {"count", "status"}
        assert {r["source_id"] for r in target} >= {"delivery"}
    assert not service.get(order.snapshot.order_id).ledger
