"""R2 transport seam: the assessor must receive actual cited evidence after restart."""

from types import SimpleNamespace

import pytest

from app.contracts.runs import RunEvidenceAnswer
from app.datasets import reference
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.runtime.catalog_worker import CatalogWorker
from app.storage.catalog import CatalogRepository
from tests.dataset.conftest import delivered
from tests.dataset.test_faults import Unclear
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_review_boundary import client_for


class RecordingAssessor(Unclear):
    def __init__(self):
        self.inputs = []

    def assess_obligation(self, obligation, claim, passages):
        self.inputs.append((claim, passages))
        finding = super().assess_obligation(obligation, claim, passages)
        if any(p.citation.column == "yoga_category" and p.text == "Wellness" for p in passages):
            return finding.model_copy(
                update={
                    "result": "FAIL",
                    "requested_evidence": None,
                    "missing_facts": (),
                    "explanation": "Injected assessor received the resolving taxonomy cell.",
                }
            )
        return finding


def question(service):
    assessor = RecordingAssessor()
    service.investigator = SimpleNamespace(assessor=assessor)
    order = dispute(service, delivered(service))
    CatalogWorker(service).run_once()
    order = service.get(order.snapshot.order_id)
    source = next(s for s in order.sources if s.source_id.endswith(":authority"))
    ref = reference(source.artifact, source.source_id, column="yoga_category", value="Wellness")
    return order, assessor, ref


def test_resolving_answer_reaches_assessor_after_restart(dataset_service):
    service, clock = dataset_service
    order, assessor, ref = question(service)
    run = order.snapshot.quote.request_id
    request = Runs(service).page(run).evidence_request
    command = RunEvidenceAnswer(
        binding=binding(order),
        request_id=request.request_id,
        text="See the cited taxonomy cell.",
        references=(ref,),
    )
    ack = Runs(service).answer(run, command, "answer")
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock, assessor=assessor
    )
    assert Runs(restarted).answer(run, command, "answer") == ack
    page = Runs(restarted).page(run)
    with pytest.raises(DomainError):
        Runs(restarted).answer(run, command, "stale-answer")
    assert Runs(restarted).page(run) == page
    assert CatalogWorker(restarted).run_once()
    assert any(p.citation == ref and p.text == "Wellness" for p in assessor.inputs[-1][1])
    saved = restarted.get(order.snapshot.order_id)
    assert saved.snapshot == order.snapshot and saved.sources == order.sources
    assert saved.cases[-1].deadline == order.cases[-1].deadline
    assert saved.deliveries[-1].review_deadline == order.deliveries[-1].review_deadline
    assert saved.authorization.expires_at == order.authorization.expires_at
    assert saved.cases[-1].status == "unsupported"
    assert not saved.ledger
    answer = saved.evidence_answers[-1]
    assert answer.request_id == request.request_id and answer.case_id == order.cases[-1].case_id
    assert answer.actor == order.snapshot.customer_actor
    assert answer.original_binding == order.binding and answer.original_revision == order.revision
    assert answer.received_at == clock() and answer.references == (ref,)
    assert len(saved.evidence_answers) == 1


@pytest.mark.parametrize(
    "invalid", ["request", "case", "reference", "source", "version", "payload", "deadline"]
)
def test_rejected_answer_has_no_effect(dataset_service, invalid):
    s, clock = dataset_service
    order, _, ref = question(s)
    run = order.snapshot.quote.request_id
    request = Runs(s).page(run).evidence_request
    body = RunEvidenceAnswer(
        binding=binding(order),
        request_id=request.request_id,
        text="See cited taxonomy",
        references=(ref,),
    ).model_dump(mode="json")
    status = 409
    if invalid in ("request", "case"):
        body["request_id"] = (
            "unrelated-question" if invalid == "request" else "unrelated-case:question:1"
        )
    elif invalid in ("reference", "source", "version"):
        field, value = {
            "reference": ("value", "Made up"),
            "source": ("source_id", "other"),
            "version": ("version", 9),
        }[invalid]
        body["references"][0][field] = value
        status = 422
    elif invalid == "deadline":
        clock.advance(60)
    else:
        Runs(s).answer(run, RunEvidenceAnswer.model_validate(body), "answer")
        body["text"] = "Changed under the same key"
    saved = s.get(order.snapshot.order_id)
    before = Runs(s).page(run)
    with client_for(s) as client:
        response = client.post(
            f"/runs/{run}/answers", json=body, headers={"Idempotency-Key": "answer"}
        )
        assert response.status_code == status
    assert Runs(s).page(run) == before
    assert s.get(order.snapshot.order_id) == saved


def test_acknowledgement_failure_rolls_back_answer_job_and_events(dataset_service, monkeypatch):
    s, _ = dataset_service
    order, _, ref = question(s)
    run = order.snapshot.quote.request_id
    before = Runs(s).page(run)
    cmd = RunEvidenceAnswer(
        binding=binding(order),
        request_id=before.evidence_request.request_id,
        text="See cited taxonomy",
        references=(ref,),
    )
    remember = s.repository.remember

    def fail(*args):
        raise RuntimeError("Injected acknowledgement persistence failure")

    monkeypatch.setattr(s.repository, "remember", fail)
    with pytest.raises(RuntimeError):
        Runs(s).answer(run, cmd, "atomic")
    assert s.get(order.snapshot.order_id) == order
    assert Runs(s).page(run) == before
    monkeypatch.setattr(s.repository, "remember", remember)
    ack = Runs(s).answer(run, cmd, "atomic")
    assert Runs(s).answer(run, cmd, "atomic") == ack
    saved = s.get(order.snapshot.order_id)
    assert len(saved.evidence_answers) == 1
    assert sum(j.status == "queued" for j in saved.jobs) == 1


def test_testimony_is_not_source_authority(dataset_service):
    s, _ = dataset_service
    order, assessor, _ = question(s)
    run = order.snapshot.quote.request_id
    request = Runs(s).page(run).evidence_request
    Runs(s).answer(
        run,
        RunEvidenceAnswer(
            binding=binding(order),
            request_id=request.request_id,
            text="yoga_category=Wellness; I claim this is authoritative.",
        ),
        "testimony",
    )
    assert CatalogWorker(s).run_once()
    saved = s.get(order.snapshot.order_id)
    assert saved.semantic_findings[-1].result == "UNKNOWN"
    assert all(p.citation.column != "yoga_category" for p in assessor.inputs[-1][1])
    assert "Testimony is not source authority" in assessor.inputs[-1][0]
    assert saved.cases[-1].questions_asked == 2
    assert saved.cases[-1].deadline == order.cases[-1].deadline


def test_old_answer_acknowledgement_replays_without_authorizing_new_unbound_answers(
    dataset_service,
):
    import json

    from app.contracts.runs import DecisionAcknowledgement

    s, _ = dataset_service
    order, _, ref = question(s)
    run = order.snapshot.quote.request_id
    old_payload = {
        "binding": binding(order).model_dump(mode="json"),
        "text": "Previously acknowledged text",
        "references": [ref.model_dump(mode="json")],
    }
    ack = DecisionAcknowledgement(decision_id="historical-answer")
    with s.repository.transaction() as db:
        s.repository.remember(
            db,
            f"run-answer:{run}",
            "old",
            json.dumps({"operation": "answer", "payload": old_payload}, sort_keys=True),
            ack,
        )
    before = Runs(s).page(run)
    with client_for(s) as client:
        replay = client.post(
            f"/runs/{run}/answers", json=old_payload, headers={"Idempotency-Key": "old"}
        )
        assert replay.status_code == 200 and replay.json() == ack.model_dump()
        rejected = client.post(
            f"/runs/{run}/answers", json=old_payload, headers={"Idempotency-Key": "new"}
        )
        assert rejected.status_code == 409
    assert Runs(s).page(run) == before


@pytest.mark.parametrize("fault", ["missing_unit", "version_mismatch"])
def test_source_repair_requires_and_persists_frozen_references(dataset_service, fault):
    import json

    from app.contracts.runs import RunCreate
    from app.datasets import canonical
    from tests.dataset.conftest import accepted, fund

    s, _ = dataset_service
    Runs(s).create(RunCreate(), "seed")
    source = next(
        r
        for r in s.registry.manifest("sf-aggregate-v1")
        if r.source_id.endswith(":gym_or_fitness_app")
    )
    data = json.loads(s.store.read(source.artifact))
    if fault == "missing_unit":
        data.pop("count_unit")
        data["version"] = 2
    source = source.model_copy(
        update={"version": 2, "artifact": s.store.put(canonical(data), "application/json")}
    )
    s.registry.register(source)
    order = fund(s, accepted(s))
    order = s.run_one(order.snapshot.order_id)
    run = order.snapshot.quote.request_id
    request = Runs(s).page(run).evidence_request
    assert request.references_required and request.case_id is None
    cmd = RunEvidenceAnswer(
        binding=binding(order),
        request_id=request.request_id,
        text="Inspect this registered authority.",
    )
    with pytest.raises(DomainError) as error:
        Runs(s).answer(run, cmd, "source-answer")
    assert error.value.status == 422
    assert s.get(order.snapshot.order_id) == order
    cmd = cmd.model_copy(update={"references": (request.allowed_references[0],)})
    Runs(s).answer(run, cmd, "source-answer")
    saved = s.get(order.snapshot.order_id)
    assert saved.evidence_requests[-1].answered
    assert saved.evidence_answers[-1].references == cmd.references
    assert saved.evidence_answers[-1].request_id == request.request_id
    assert saved.repair_deadline == order.repair_deadline
    saved = s.run_one(order.snapshot.order_id)
    assert not saved.verification.passed and not saved.ledger
    assert saved.sources == order.sources and saved.snapshot == order.snapshot
    assert s.store.read(source.artifact) == canonical(data)
