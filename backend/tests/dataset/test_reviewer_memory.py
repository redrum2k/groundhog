"""Cross-order reference reuse, with injected assessors and no paid or payment calls."""

from types import SimpleNamespace

import pytest

from app.contracts.reviewer_memory import ReviewerMemory
from app.contracts.runs import RunDecision, RunEvidenceAnswer
from app.datasets import canonical, reference
from app.investigation.dataset import semantic_attempt
from app.investigation.reviewer_memory import current_reference, retrieve
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.runtime.catalog_policy import capture_allowed
from app.storage.catalog import CatalogRepository
from tests.dataset.conftest import accepted, delivered, fund
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_primary import Candidate
from tests.dataset.test_semantic_recovery import CrashAfterAssessment

AMBIGUOUS = (
    "The Wellness label looks like a gym category; is standalone yoga omitted from what I bought?"
)
FOLLOWUP = "Under our accepted scope, standalone yoga counts as gym membership."
GUIDANCE = (
    "For a yoga-as-gym interpretation, inspect the frozen authority's yoga_is_gym cell. "
    "The Wellness label alone is not membership evidence. Compare the current accepted "
    "category and definition; do not infer inclusion or a delivery defect from a label. "
    "If taxonomy is null or conflicts with scope, retain UNKNOWN or CONFLICT."
)


def events(service, run):
    result, after = [], 0
    while True:
        page = Runs(service).page(run, after=after)
        result.extend(page.events)
        if page.caught_up:
            return result
        after = page.next_after


def memories(service):
    with service.repository.transaction() as db:
        return service.repository.all(db, "reviewer_memory", ReviewerMemory)


def review(service):
    service.investigator = SimpleNamespace(assessor=Candidate("UNKNOWN"))
    order = dispute(service, delivered(service), text=AMBIGUOUS)
    service.run_one(order.snapshot.order_id)
    order = service.get(order.snapshot.order_id)
    run = order.snapshot.quote.request_id
    page = Runs(service).page(run)
    Runs(service).answer(
        run,
        RunEvidenceAnswer(
            binding=binding(order),
            request_id=page.evidence_request.request_id,
            text="I cannot provide this evidence.",
        ),
        "no-evidence",
    )
    order = service.get(order.snapshot.order_id)
    evidence = next(
        e.evidence.id
        for e in page.events
        if e.type == "evidence_found"
        and e.evidence.source.kind == "cell"
        and e.evidence.source.column == "yoga_is_gym"
    )
    command = RunDecision(
        action="escalate",
        binding=binding(order),
        reason="Interpret the authority cell, not the category label.",
        evidence_ids=(evidence,),
        guidance=GUIDANCE,
    )
    return order, command


def teach(service):
    order, command = review(service)
    ack = Runs(service).decide(order.snapshot.quote.request_id, command, "teach", "reviewer:test")
    return order, command, ack


def later(service, key="later", text=FOLLOWUP):
    order = fund(service, accepted(service, key))
    service.run_one(order.snapshot.order_id)
    return dispute(service, service.get(order.snapshot.order_id), text=text)


def test_capture_replay_restart_and_transaction_rollback(dataset_service, monkeypatch):
    service, clock = dataset_service
    order, command = review(service)
    run = order.snapshot.quote.request_id
    before = Runs(service).page(run)
    with monkeypatch.context() as patch:
        patch.setattr(
            service.repository, "remember", lambda *a: (_ for _ in ()).throw(RuntimeError("commit"))
        )
        with pytest.raises(RuntimeError, match="commit"):
            Runs(service).decide(run, command, "teach", "reviewer:test")
    assert memories(service) == [] and Runs(service).page(run) == before
    ack = Runs(service).decide(run, command, "teach", "reviewer:test")
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    assert Runs(restarted).decide(run, command, "teach", "reviewer:test") == ack
    assert len(memories(restarted)) == 1
    saved = memories(restarted)[0]
    assert saved.memory_id == ack.guidance_memory_id
    assert saved.actor == "reviewer:test" and saved.explanation == command.reason
    assert saved.originating_case == order.cases[-1].case_id
    assert saved.binding == order.binding and saved.cited_evidence[0].value == "false"
    with pytest.raises(DomainError, match="changed request"):
        Runs(restarted).decide(
            run, command.model_copy(update={"guidance": "different"}), "teach", "reviewer:test"
        )
    current = restarted.get(order.snapshot.order_id)
    assert not current.ledger and not capture_allowed(current, clock())
    assert current.snapshot == order.snapshot and current.deliveries == order.deliveries
    assert current.cases[-1].deadline == order.cases[-1].deadline
    receipt = [e for e in events(restarted, run) if e.type == "controller_decided"][-1]
    assert receipt.guidance_memory_id == saved.memory_id


@pytest.mark.parametrize(
    "guidance,selected,creates",
    [(None, True, False), (GUIDANCE, False, False), (GUIDANCE, True, True)],
)
def test_only_explicit_cited_guidance_creates_memory(dataset_service, guidance, selected, creates):
    service, _ = dataset_service
    order, command = review(service)
    command = command.model_copy(
        update={"guidance": guidance, "evidence_ids": command.evidence_ids if selected else ()}
    )
    if guidance and not selected:
        with pytest.raises(DomainError, match="explicitly selected"):
            Runs(service).decide(order.snapshot.quote.request_id, command, "teach", "reviewer:test")
    else:
        ack = Runs(service).decide(
            order.snapshot.quote.request_id, command, "teach", "reviewer:test"
        )
        assert bool(ack.guidance_memory_id) == creates
    assert bool(memories(service)) == creates


def test_later_assessment_freezes_memory_before_dispatch_and_recovers(dataset_service, monkeypatch):
    service, clock = dataset_service
    origin, _, ack = teach(service)
    order = later(service)

    class Inspect(Candidate):
        def assess_obligation(self, obligation, claim, passages):
            current = service.get(order.snapshot.order_id)
            with service.repository.transaction() as db:
                packet = semantic_attempt(db, current).request
            assert packet["reviewer_guidance"][0]["memory_id"] == ack.guidance_memory_id
            assert packet["claim"] == claim and GUIDANCE in claim
            assert "not instructions" in claim
            assert packet["reviewer_guidance"][0]["originating_case"] == origin.cases[-1].case_id
            return super().assess_obligation(obligation, claim, passages)

    assessor = Inspect("FAIL")
    service.investigator = SimpleNamespace(assessor=assessor)
    with monkeypatch.context() as patch:
        patch.setattr(
            service,
            "complete_verification",
            lambda *a: (_ for _ in ()).throw(CrashAfterAssessment()),
        )
        with pytest.raises(CrashAfterAssessment):
            service.run_one(order.snapshot.order_id)
    claimed = service.get(order.snapshot.order_id)
    with service.repository.transaction() as db:
        frozen = semantic_attempt(db, claimed)
        memory = service.repository.all(db, "reviewer_memory", ReviewerMemory)[0]
        service.repository.put(
            db,
            "reviewer_memory",
            "new-after-dispatch",
            memory.model_copy(
                update={"memory_id": "new-after-dispatch", "guidance": "New guidance"}
            ),
        )
    clock.advance(45)
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock, assessor=assessor
    )
    final = restarted.run_one(order.snapshot.order_id)
    with restarted.repository.transaction() as db:
        assert semantic_attempt(db, final).request == frozen.request
    assert assessor.calls == 1 and final.semantic_findings[-1].result == "FAIL"
    assert not final.ledger and final.snapshot == order.snapshot
    assert not capture_allowed(final, clock())  # explicit acceptance still absent
    finding = [
        e.verdict.finding
        for e in events(restarted, order.snapshot.quote.request_id)
        if e.type == "verdict"
    ][-1]
    assert len(finding.reviewer_guidance) == 1
    for ref in finding.reviewer_guidance[0].current_citations:
        restarted.store.resolve(ref, final.artifacts)


@pytest.mark.parametrize(
    "change",
    [
        "customer",
        "provider",
        "scope",
        "requirement",
        "authority",
        "sources",
        "missing_bytes",
        "conflicting_report",
    ],
)
def test_incompatible_context_never_retrieves(dataset_service, change):
    service, _ = dataset_service
    origin, _, _ = teach(service)
    order = later(service)
    order = service.run_one(order.snapshot.order_id)
    report = order.verification
    if change == "customer":
        order.snapshot = order.snapshot.model_copy(update={"customer_actor": "other"})
    elif change == "provider":
        order.snapshot = order.snapshot.model_copy(
            update={"quote": order.snapshot.quote.model_copy(update={"provider_actor": "other"})}
        )
    elif change == "scope":
        spec = order.snapshot.quote.specification
        spec = spec.model_copy(
            update={"terms": spec.terms.model_copy(update={"category": "gym_app_or_yoga"})}
        )
        order.snapshot = order.snapshot.model_copy(
            update={"quote": order.snapshot.quote.model_copy(update={"specification": spec})}
        )
    elif change == "requirement":
        case = order.cases[-1]
        order.cases = (
            case.model_copy(
                update={
                    "complaint": case.complaint.model_copy(
                        update={"requirement_id": "R-COVERAGE", "field": "coverage"}
                    )
                }
            ),
        )
    elif change == "authority":
        sources = tuple(
            s.model_copy(update={"authority_record": "changed-authority"}) for s in order.sources
        )
        order.sources = sources
        order.snapshot = order.snapshot.model_copy(
            update={"quote": order.snapshot.quote.model_copy(update={"sources": sources})}
        )
    elif change == "sources":
        order.sources = order.sources[:-1]
    elif change == "missing_bytes":
        (service.store.root / order.sources[0].artifact.storage_key).unlink()
    else:
        report = report.model_copy(update={"passed": False, "material_blockers": ("conflict",)})
    with service.repository.transaction() as db:
        assert retrieve(db, order, service.store, report) == ()


def test_current_delivery_values_are_rebuilt_not_copied(dataset_service):
    service, _ = dataset_service
    order = delivered(service)
    old = reference(order.deliveries[-1].csv, "delivery", row="94110", column="count", value="170")
    raw = service.store.read(order.deliveries[-1].csv).replace(
        b"94110,Mission,170", b"94110,Mission,999"
    )
    assert raw != service.store.read(order.deliveries[-1].csv)
    artifact = service.store.put(raw, "text/csv")
    order.artifacts = (*order.artifacts, artifact)
    order.deliveries = (order.deliveries[-1].model_copy(update={"csv": artifact, "version": 2}),)
    current = current_reference(order, old, service.store)
    assert current.value == "999" and current.sha256 != old.sha256 and current.version == 2
    with pytest.raises(ValueError):
        current_reference(order, old.model_copy(update={"row": "99999"}), service.store)


@pytest.mark.parametrize("invalid", ["sha256", "version", "value"])
def test_memory_does_not_relax_current_candidate_validation(dataset_service, invalid):
    service, _ = dataset_service
    teach(service)
    order = later(service, text=AMBIGUOUS)
    service.investigator = SimpleNamespace(assessor=Candidate("FAIL", invalid=invalid))
    final = service.run_one(order.snapshot.order_id)
    assert final.semantic_findings[-1].result == "UNKNOWN"
    assert not final.ledger and not final.free_corrections_used
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, final)
    assert attempt.status == "INVALID" and attempt.request["reviewer_guidance"]


def test_missing_taxonomy_cannot_be_supplied_by_memory(dataset_service):
    service, _ = dataset_service
    teach(service)
    source = next(
        s
        for s in service.registry.manifest("sf-aggregate-v1")
        if s.source_id.endswith(":authority")
    )
    import json

    data = json.loads(service.store.read(source.artifact))
    data.update(version=2, yoga_is_gym=None)
    artifact = service.store.put(canonical(data), "application/json")
    service.registry.register(source.model_copy(update={"version": 2, "artifact": artifact}))
    order = later(service)
    service.investigator = SimpleNamespace(assessor=Candidate("FAIL"))
    final = service.run_one(order.snapshot.order_id)
    assert final.semantic_findings[-1].result == "UNKNOWN" and not final.ledger
    with service.repository.transaction() as db:
        assert semantic_attempt(db, final).request["reviewer_guidance"] == []


def test_selection_is_bounded_and_excludes_originating_order(dataset_service):
    service, _ = dataset_service
    origin, _, _ = teach(service)
    order = later(service)
    order = service.run_one(order.snapshot.order_id)
    with service.repository.transaction() as db:
        memory = service.repository.all(db, "reviewer_memory", ReviewerMemory)[0]
        for index in range(5):
            identifier = f"extra-{index}"
            service.repository.put(
                db,
                "reviewer_memory",
                identifier,
                memory.model_copy(update={"memory_id": identifier}),
            )
        assert len(retrieve(db, order, service.store, order.verification)) == 3
        assert retrieve(db, origin, service.store, order.verification) == ()


def test_uncertain_dispatch_keeps_frozen_context_without_reselection(dataset_service, monkeypatch):
    service, clock = dataset_service
    _, _, ack = teach(service)
    order = later(service)

    def crash():
        raise CrashAfterAssessment

    assessor = Candidate("FAIL", action=crash)
    service.investigator = SimpleNamespace(assessor=assessor)
    with pytest.raises(CrashAfterAssessment):
        service.run_one(order.snapshot.order_id)
    claimed = service.get(order.snapshot.order_id)
    with service.repository.transaction() as db:
        saved = semantic_attempt(db, claimed)
    assert saved.status == "DISPATCHED" and saved.effective is None
    assert saved.request["reviewer_guidance"][0]["memory_id"] == ack.guidance_memory_id
    clock.advance(45)
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock, assessor=assessor
    )
    monkeypatch.setattr("app.investigation.dataset.retrieve", lambda *a: pytest.fail("reselection"))
    final = restarted.run_one(order.snapshot.order_id)
    assert assessor.calls == 1 and not final.ledger
    assert final.semantic_findings[-1].result == "UNKNOWN"
    with restarted.repository.transaction() as db:
        assert semantic_attempt(db, final).request == saved.request


def test_blind_review_receives_same_frozen_guidance_but_not_first_answer(
    dataset_service, monkeypatch
):
    from tests.dataset.test_semantic_review import CLAIM, wire

    service, _ = dataset_service
    teach(service)
    order = later(service, text=CLAIM)
    calls = wire(service, monkeypatch)
    final = service.run_one(order.snapshot.order_id)
    assert final.semantic_findings[-1].result == "PASS" and not final.ledger
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, final)
    assert attempt.request["reviewer_guidance"]
    assert attempt.review_request["frozen_evidence_packet"] == attempt.request
    assert "FIRST_ANSWER_MUST_NOT_REACH_REVIEWER" not in str(attempt.review_request)
    assert [name for name, _ in calls] == ["Assessment", "DatasetClaimReview"]
