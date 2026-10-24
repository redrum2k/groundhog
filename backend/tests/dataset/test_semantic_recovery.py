"""Completed semantic work survives a pure lease reclaim, never an evidence change."""

from types import SimpleNamespace

import pytest

from app.investigation.dataset import semantic_attempt
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_primary import Candidate, make_delivery


class CrashAfterAssessment(BaseException):
    pass


def completed_before_crash(service, monkeypatch, result="FAIL"):
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    candidate = Candidate(result)
    service.investigator = SimpleNamespace(assessor=candidate)
    original = dispute(
        service,
        make_delivery(service, expanded=result == "PASS"),
        text="Yoga is included in the agreed gym/app definition.",
    )

    def crash(*args, **kwargs):
        raise CrashAfterAssessment

    with monkeypatch.context() as patch:
        patch.setattr(service, "complete_verification", crash)
        with pytest.raises(CrashAfterAssessment):
            service.run_one(original.snapshot.order_id)
    claimed = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, claimed)
    assert attempt.status == "VALIDATED" and attempt.effective.result == result
    assert not claimed.semantic_findings and candidate.calls == 1
    return claimed, attempt, candidate


@pytest.mark.parametrize("result", ["FAIL", "PASS", "UNKNOWN"])
def test_restart_reuses_completed_assessment_after_lease_reclaim(
    dataset_service, monkeypatch, result
):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch, result)
    clock.advance(45)
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock, assessor=candidate
    )
    final = restarted.run_one(original.snapshot.order_id)
    assert final.semantic_findings[-1] == saved.effective
    assert candidate.calls == 1
    assert final.snapshot == original.snapshot and final.sources == original.sources
    assert final.cases[-1].deadline == original.cases[-1].deadline
    assert not final.ledger and not final.free_corrections_used
    assert final.cases[-1].questions_asked == (1 if result == "UNKNOWN" else 0)
    if result == "FAIL":
        assert final.cases[-1].status == "unsupported"
    with restarted.repository.transaction() as db:
        retained = semantic_attempt(db, original)
    assert retained.order_revision == saved.order_revision
    assert retained.request == saved.request and retained.candidate == saved.candidate
    assert retained.effective == saved.effective and retained.status == saved.status
