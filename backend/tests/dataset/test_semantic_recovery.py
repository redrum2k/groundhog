"""Completed semantic work survives a pure lease reclaim, never an evidence change."""

import json
from types import SimpleNamespace

import pytest

from app.contracts.catalog import CatalogOrder
from app.investigation.dataset import semantic_attempt
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository, DomainError
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_primary import Candidate, make_delivery


class CrashAfterAssessment(BaseException):
    pass


def completed_before_crash(service, monkeypatch, result="FAIL", invalid=None):
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    candidate = Candidate(result, invalid=invalid)
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
    assert attempt.status == ("FAILED" if invalid else "VALIDATED")
    assert attempt.effective.result == result
    assert not claimed.semantic_findings and candidate.calls == 1
    return claimed, attempt, candidate


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize(
    "result,invalid", [("FAIL", None), ("PASS", None), ("UNKNOWN", None), ("FAIL", "timeout")]
)
def test_restart_reuses_completed_assessment_after_lease_reclaim(
    dataset_service, monkeypatch, result, invalid, legacy
):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch, result, invalid)
    if legacy:
        data = saved.model_dump(mode="json")
        data.pop("recovery_revisions")
        with service.repository.transaction() as db:
            db.execute(
                "UPDATE catalog_records SET data=? WHERE kind='dataset_assessment' AND id=?",
                (json.dumps(data), saved.attempt_id),
            )
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
    assert retained.recovery_revisions == (saved.order_revision + 1,)
    assert retained.request == saved.request and retained.candidate == saved.candidate
    assert retained.effective == saved.effective and retained.status == saved.status


def test_superseded_worker_cannot_poison_recovered_completed_result(dataset_service, monkeypatch):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    old_job = next(j for j in original.jobs if j.status == "running")
    clock.advance(45)
    reclaimed, new_job = service.claim_job(original.snapshot.order_id)
    assert new_job.job_id == old_job.job_id and new_job.lease_token != old_job.lease_token
    with pytest.raises(DomainError, match="lease"):
        service.run_dataset(original, old_job)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, original)
    assert attempt.status == "VALIDATED" and attempt.effective == saved.effective
    final = service.run_dataset(reclaimed, new_job)
    assert final.semantic_findings[-1] == saved.effective and candidate.calls == 1
    assert final.cases[-1].status == "unsupported" and not final.ledger


def test_claim_rollback_also_rolls_back_recovery_revision(dataset_service, monkeypatch):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    clock.advance(45)

    def fail_save(*args, **kwargs):
        raise RuntimeError("synthetic claim commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(service, "_save", fail_save)
        with pytest.raises(RuntimeError, match="claim commit"):
            service.claim_job(original.snapshot.order_id)
    with service.repository.transaction() as db:
        assert semantic_attempt(db, original) == saved
        current = service.repository.load(db, "order", original.snapshot.order_id, CatalogOrder)
    assert current.revision == original.revision and current.jobs == original.jobs
    final = service.run_one(original.snapshot.order_id)
    assert final.semantic_findings[-1] == saved.effective and candidate.calls == 1


def test_unrelated_revision_is_not_laundered_by_reclaim(dataset_service, monkeypatch):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    with service.repository.transaction() as db:
        current = service.repository.load(db, "order", original.snapshot.order_id, CatalogOrder)
        current.revision += 1  # Fault injection: not the worker's own claim transition.
        service.repository.put(db, "order", original.snapshot.order_id, current)
    clock.advance(45)
    final = service.run_one(original.snapshot.order_id)
    assert final.semantic_findings[-1].result == "UNKNOWN" and candidate.calls == 1
    assert final.cases[-1].status != "unsupported" and not final.ledger
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, original)
    assert not attempt.recovery_revisions and attempt.status == "STALE"
    assert attempt.candidate == saved.candidate and attempt.order_revision == saved.order_revision


@pytest.mark.parametrize("change", ["complaint", "terms", "binding"])
def test_changed_semantic_input_cannot_rebase_old_result(dataset_service, monkeypatch, change):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    with service.repository.transaction() as db:
        current = service.repository.load(db, "order", original.snapshot.order_id, CatalogOrder)
        # Fault injection even without a revision bump: the content key remains a separate guard.
        if change == "complaint":
            case = current.cases[-1]
            current.cases = (
                *current.cases[:-1],
                case.model_copy(
                    update={
                        "complaint": case.complaint.model_copy(
                            update={"text": "Yoga should be executive-ready."}
                        )
                    }
                ),
            )
        elif change == "terms":
            quote = current.snapshot.quote
            spec = quote.specification
            changed = spec.model_copy(
                update={
                    "terms": spec.terms.model_copy(
                        update={
                            "category_meaning": "Changed meaning for stale-guard fault injection."
                        }
                    )
                }
            )
            current.snapshot = current.snapshot.model_copy(
                update={"quote": quote.model_copy(update={"specification": changed})}
            )
        else:
            current.binding = current.binding.model_copy(
                update={"evidence_revision": current.binding.evidence_revision + 1}
            )
        service.repository.put(db, "order", original.snapshot.order_id, current)
    clock.advance(45)
    if change == "binding":
        with pytest.raises(DomainError, match="no dispatchable work"):
            service.claim_job(original.snapshot.order_id)
    else:
        claimed, _ = service.claim_job(original.snapshot.order_id)
        with service.repository.transaction() as db:
            assert semantic_attempt(db, claimed) is None
    with service.repository.transaction() as db:
        assert semantic_attempt(db, original) == saved
    assert candidate.calls == 1


def test_expired_case_cannot_recover_or_extend_completed_work(dataset_service, monkeypatch):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    clock.value = original.cases[-1].deadline
    with pytest.raises(DomainError):
        service.claim_job(original.snapshot.order_id)
    final = service.get(original.snapshot.order_id)
    assert final.cases[-1].deadline == original.cases[-1].deadline
    assert not final.ledger and not final.free_corrections_used and candidate.calls == 1
    with service.repository.transaction() as db:
        assert semantic_attempt(db, original) == saved


def test_uncertain_dispatch_is_not_recovered_as_completed_or_retried(dataset_service, monkeypatch):
    service, clock = dataset_service
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")

    def crash():
        raise CrashAfterAssessment

    candidate = Candidate("FAIL", action=crash)
    service.investigator = SimpleNamespace(assessor=candidate)
    original = dispute(
        service, make_delivery(service), text="Yoga is included in the agreed gym/app definition."
    )
    with pytest.raises(CrashAfterAssessment):
        service.run_one(original.snapshot.order_id)
    original = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, original)
    assert attempt.status == "DISPATCHED" and attempt.effective is None
    clock.advance(45)
    final = service.run_one(original.snapshot.order_id)
    assert candidate.calls == 1 and final.semantic_findings[-1].result == "UNKNOWN"
    assert not final.ledger and not final.free_corrections_used
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, original)
    assert not attempt.recovery_revisions and attempt.candidate is None


def test_previously_stale_result_does_not_regain_authority(dataset_service, monkeypatch):
    service, clock = dataset_service
    original, saved, candidate = completed_before_crash(service, monkeypatch)
    with service.repository.transaction() as db:
        service.repository.put(
            db, "dataset_assessment", saved.attempt_id, saved.model_copy(update={"status": "STALE"})
        )
    clock.advance(45)
    final = service.run_one(original.snapshot.order_id)
    assert candidate.calls == 1 and final.semantic_findings[-1].result == "UNKNOWN"
    assert final.cases[-1].status != "unsupported" and not final.ledger
    with service.repository.transaction() as db:
        assert not semantic_attempt(db, original).recovery_revisions
