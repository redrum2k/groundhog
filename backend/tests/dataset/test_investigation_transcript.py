"""Persisted transcript projection; synthetic model transports, no provider calls."""

import pytest

from app.orders.runs import Runs
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_primary import make_delivery
from tests.dataset.test_semantic_review import CLAIM, wire


@pytest.mark.parametrize("mode", ["model", "disagreement", "rules"])
def test_complaint_and_effective_finding_are_visible_without_inventing_authority(
    dataset_service, monkeypatch, mode
):
    service, _ = dataset_service
    claim = "Yoga should count as fitness" if mode == "rules" else CLAIM
    before = dispute(service, make_delivery(service), text=claim)
    if mode != "rules":
        wire(service, monkeypatch, invalid="disagree" if mode == "disagreement" else None)
    else:
        monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "false")
    assert CatalogWorker(service).run_once()
    current = service.get(before.snapshot.order_id)
    events = Runs(service).page(current.snapshot.quote.request_id).events
    buyer = [e for e in events if e.type == "message" and e.message.text == claim]
    assert len(buyer) == 1 and buyer[0].message.from_ == "buyer"
    verdict = next(e for e in reversed(events) if e.type == "verdict")
    finding = verdict.verdict.finding
    messages = [e for e in events if e.type == "message" and e.step == "verdict"]
    assert len(messages) == 1
    message = messages[0].message
    assert claim in message.text
    assert f"Finding: {finding.effective.result}" in message.text
    assert f"Provenance: {finding.decided_by}" in message.text
    assert finding.effective.explanation in message.text
    assert "does not authorize payment" in message.text
    assert [a.evidenceId for a in message.attach] == finding.evidence_ids
    assert any(e.type == "step_completed" and e.step == "verdict" for e in events)
    completed = any(e.type == "step_completed" and e.step == "investigate" for e in events)
    assert completed == (mode != "disagreement")
    if mode == "disagreement":
        assert finding.decided_by == "unresolved" and finding.effective.result == "UNKNOWN"
        assert "Finding: PASS" not in message.text  # Raw model suggestion is not the outcome.
        assert current.cases[-1].question
    else:
        assert finding.decided_by == mode
    assert current.snapshot == before.snapshot and not current.ledger
    assert current.cases[-1].deadline == before.cases[-1].deadline
    assert not CatalogWorker(service).run_once()
    assert Runs(service).page(current.snapshot.quote.request_id).events == events
