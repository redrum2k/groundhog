import pytest
from fastapi.testclient import TestClient
from tools.learning_examples import example_bundle

from app.contracts.catalog import AcceptQuoteCommand, QuoteRequest, RevisionCommand
from app.contracts.source_learning import LearningCommand, ResolveSource
from app.learning.service import OWNER
from app.main import create_app
from app.orders.service import DomainError
from tests.source_learning.test_live_learning import compile, create, trained


def activate(learning, candidate):
    learning.qualify(LearningCommand(idempotency_key="q", target_id=candidate), "controller")
    result = learning.transition(
        LearningCommand(idempotency_key="a", target_id=candidate), "controller", "approve"
    )
    learning.transition(
        LearningCommand(idempotency_key="on", target_id=result.record_id), "controller", "activate"
    )
    return result.record_id


def test_replay_survives_resolution_and_success_and_rejects_changed_payload(live):
    service, learning = live
    learning.publish(example_bundle(service.clock()), "worker")
    request = create(service, "retry")
    command = RevisionCommand(expected_revision=1, idempotency_key="original")
    held = service.compile_request(request, command)
    assert service.compile_request(request, command) == held
    for review, column in zip(learning.state().reviews, ("v_count", "p_adults"), strict=True):
        resolution = ResolveSource(
            idempotency_key=column,
            encounter_id=review.encounter_id,
            column=column,
            explanation="Simulated source-owner evidence.",
        )
        result = learning.resolve(resolution, OWNER)
        assert learning.resolve(resolution, OWNER) == result
    final_command = RevisionCommand(
        expected_revision=service.get_request(request).revision, idempotency_key="final"
    )
    ready = service.compile_request(request, final_command)
    assert ready.status == "ready"
    assert service.compile_request(request, final_command) == ready
    assert service.compile_request(request, command) == held
    with pytest.raises(DomainError, match="changed request"):
        service.compile_request(request, final_command.model_copy(update={"expected_revision": 99}))


def test_revocation_blocks_pending_acceptance_without_touching_money(live):
    service, learning = live
    _, candidate = trained(live)
    version = activate(learning, candidate)
    request = create(service, "pending-consent")
    draft = compile(service, request, "c")
    quote = service.issue_quote(
        request, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
    )
    learning.transition(
        LearningCommand(idempotency_key="off", target_id=version), "controller", "revoke"
    )
    with pytest.raises(DomainError, match="no longer active"):
        service.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="accept"
            )
        )
    with service.repository.transaction() as db:
        assert (
            db.execute("SELECT count(*) FROM catalog_records WHERE kind='order'").fetchone()[0] == 0
        )


def test_conflicting_new_owner_evidence_blocks_an_old_active_component(live):
    service, learning = live
    _, candidate = trained(live)
    pending = create(service, "preapproval-held")
    assert compile(service, pending, "held").status == "human_review"
    review = next(r for r in learning.state().reviews if r.request_id == pending)
    activate(learning, candidate)
    learning.resolve(
        ResolveSource(
            idempotency_key="contradiction",
            encounter_id=review.encounter_id,
            column="v_devices",
            explanation="Simulated contradictory owner correction; must block reuse.",
        ),
        OWNER,
    )
    future = create(service, "conflicting-history")
    assert compile(service, future, "block").status == "human_review"
    assert any(
        r.reason == "conflicting_retained_definition"
        for r in learning.state().reviews
        if r.request_id == future
    )


def test_independent_oracle_rejects_corrupted_normalization(live, monkeypatch):
    from app.agents.source_knowledge import SourceKnowledge

    _, learning = live
    _, candidate = trained(live)
    real = SourceKnowledge.assess

    def corrupted(engine, case):
        result = real(engine, case)
        if result["normalized"]:
            row = next(r for r in result["normalized"]["rows"] if r["status"] == "released")
            row["count"] += 1
        return result

    monkeypatch.setattr(SourceKnowledge, "assess", corrupted)
    result = learning.qualify(
        LearningCommand(idempotency_key="bad", target_id=candidate), "controller"
    )
    assert result.status == "REJECTED"
    assert not learning.state().qualification.passed
    with pytest.raises(DomainError, match="qualification"):
        learning.transition(
            LearningCommand(idempotency_key="no-approve", target_id=candidate),
            "controller",
            "approve",
        )


def test_local_profile_rejects_remote_clients_and_financial_fields(tmp_path):
    app = create_app(
        tmp_path / "db",
        artifact_root=tmp_path / "bytes",
        run_worker=False,
        source_learning=True,
        internal_token="worker",
        reviewer_token="controller",
        source_owner_token="owner",
    )
    with TestClient(app, client=("198.51.100.1", 5000)) as client:
        assert (
            client.post(
                "/runs",
                json={"prompt": "anything", "corpus_id": "sf-aggregate-v1"},
                headers={"Idempotency-Key": "x"},
            ).status_code
            == 403
        )
    with pytest.raises(ValueError):
        LearningCommand(idempotency_key="x", target_id="y", payment_authority="capture")


def test_new_order_specific_resolution_is_not_mislabeled_as_old_version_reuse(live):
    from datetime import timedelta

    from app.catalog.preparation import PreparedSources

    service, learning = live
    _, candidate = trained(live)
    version = activate(learning, candidate)
    # A distinct current authority requires fresh owner evidence.
    learning.publish(example_bundle(service.clock() + timedelta(minutes=1), 2), "worker")
    request = create(service, "new-authority-needs-owner")
    assert compile(service, request, "held").status == "human_review"
    reviews = [r for r in learning.state().reviews if r.request_id == request]
    for review, column in zip(reviews, ("v_count", "p_adults"), strict=True):
        learning.resolve(
            ResolveSource(
                idempotency_key="new-" + column,
                encounter_id=review.encounter_id,
                column=column,
                explanation="New independent owner authorization for changed dictionary.",
            ),
            OWNER,
        )
    assert compile(service, request, "owner-prepared").status == "ready"
    with service.repository.transaction() as db:
        prepared = service.repository.load(db, "prepared_sources", request, PreparedSources)
        assert prepared.learning_version is None
    assert learning.state().active_version == version
    assert not [
        e
        for e in learning.state().events
        if e.request_id == request and e.kind == "knowledge_reused"
    ]


def test_changed_code_disables_reuse_but_controller_can_retire_old_version(live, monkeypatch):
    from app.learning import service as module

    service, learning = live
    _, candidate = trained(live)
    version = activate(learning, candidate)
    monkeypatch.setattr(module, "implementation_digest", lambda: "f" * 64)
    with pytest.raises(DomainError, match="restart"):
        learning.state()
    restarted = module.SourceLearning(service, enabled=True)
    service.source_learning = restarted
    assert restarted.state().active_version == version
    assert not restarted.state().active_current
    request = create(service, "code-upgraded")
    assert compile(service, request, "hold").status == "human_review"
    restarted.transition(
        LearningCommand(idempotency_key="retire-stale", target_id=version), "controller", "revoke"
    )
    assert restarted.state().active_version is None


def test_qualification_preserves_registered_authority_version(live):
    from datetime import timedelta

    service, learning = live
    trained(live)
    new_bundle = learning.publish(
        example_bundle(service.clock() + timedelta(minutes=1), 2), "worker"
    )
    request = create(service, "dictionary-v2")
    assert compile(service, request, "hold-v2").status == "human_review"
    reviews = [r for r in learning.state().reviews if r.request_id == request]
    for review, column in zip(reviews, ("v_count", "p_adults"), strict=True):
        learning.resolve(
            ResolveSource(
                idempotency_key="v2-" + column,
                encounter_id=review.encounter_id,
                column=column,
                explanation="Independent simulated owner evidence for dictionary version 2.",
            ),
            OWNER,
        )
    candidate = learning.propose(
        LearningCommand(idempotency_key="candidate-v2", target_id=new_bundle.record_id), "worker"
    )
    report = learning.qualify(
        LearningCommand(idempotency_key="qualify-v2", target_id=candidate.record_id), "controller"
    )
    assert report.status == "QUALIFIED"


@pytest.mark.parametrize("stage", ["quote", "accept"])
def test_code_upgrade_blocks_previously_prepared_learning_at_consent(live, monkeypatch, stage):
    from app.learning import service as module

    service, learning = live
    _, candidate = trained(live)
    activate(learning, candidate)
    request = create(service, "prepared-before-upgrade")
    draft = compile(service, request, "prepare")
    if stage == "accept":
        quote = service.issue_quote(
            request, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
        )
    monkeypatch.setattr(module, "implementation_digest", lambda: "f" * 64)
    service.source_learning = module.SourceLearning(service, enabled=True)
    assert not service.source_learning.state().active_current
    with pytest.raises(DomainError, match="implementation"):
        if stage == "quote":
            service.issue_quote(
                request, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
            )
        else:
            service.accept_quote(
                AcceptQuoteCommand(
                    quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="accept"
                )
            )


def test_failed_owner_command_does_not_commit_training_evidence(live, monkeypatch):
    service, learning = live
    learning.publish(example_bundle(service.clock()), "worker")
    request = create(service, "atomic-owner-command")
    before = compile(service, request, "hold")
    review = learning.state().reviews[0]
    command = ResolveSource(
        idempotency_key="atomic-resolution",
        encounter_id=review.encounter_id,
        column="v_count",
        explanation="Simulated owner correction; commit only with the whole command.",
    )
    real_event = learning._event

    def fail_event(*args, **kwargs):
        raise RuntimeError("injected event persistence failure")

    monkeypatch.setattr(learning, "_event", fail_event)
    with pytest.raises(RuntimeError, match="injected"):
        learning.resolve(command, OWNER)
    assert learning.memory.records("source_resolution") == []
    assert learning.memory.records("source_procedure") == []
    assert service.get_request(request) == before
    monkeypatch.setattr(learning, "_event", real_event)
    result = learning.resolve(command, OWNER)
    assert learning.resolve(command, OWNER) == result
    assert len(learning.memory.records("source_resolution")) == 1
    assert len(learning.memory.records("source_procedure")) == 1


def test_concurrent_changed_owner_command_cannot_leave_rejected_evidence(live):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    service, learning = live
    learning.publish(example_bundle(service.clock()), "worker")
    request = create(service, "concurrent-owner-command")
    compile(service, request, "hold")
    review = learning.state().reviews[0]
    barrier = Barrier(2)

    def submit(column):
        barrier.wait(timeout=5)
        try:
            return learning.resolve(
                ResolveSource(
                    idempotency_key="same-key",
                    encounter_id=review.encounter_id,
                    column=column,
                    explanation="Simulated competing owner command.",
                ),
                OWNER,
            )
        except DomainError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ("v_count", "v_devices")))
    assert sum(isinstance(r, DomainError) for r in results) == 1
    assert len(learning.memory.records("source_resolution")) == 1
    assert len(learning.memory.records("source_procedure")) == 1


@pytest.mark.parametrize("stage", ["quote", "accept"])
@pytest.mark.parametrize("second_source", ["public_definition", "owner_answer"])
def test_mixed_preparation_retains_revocable_learning_dependency(live, stage, second_source):
    from app.catalog.preparation import PreparedSources
    from app.contracts.source_learning import BundleUpload

    service, learning = live
    _, candidate = trained(live)
    version = activate(learning, candidate)
    bundle = example_bundle(service.clock(), 2).model_dump(mode="json")
    authority = bundle["partitions"][1]["authority"]
    authority["epoch"] = "new-second-partition-authority"
    if second_source == "public_definition":
        authority["definitions"] = [{"column": "p_adults", "unit": "unique_adults_per_zip"}]
    learning.publish(BundleUpload.model_validate(bundle), "worker")
    request = create(service, "mixed-sources")
    draft = compile(service, request, "mixed-compile")
    if second_source == "owner_answer":
        review = next(r for r in learning.state().reviews if r.request_id == request)
        learning.resolve(
            ResolveSource(
                idempotency_key="new-second-source-answer",
                encounter_id=review.encounter_id,
                column="p_adults",
                explanation="Current simulated owner evidence.",
            ),
            OWNER,
        )
        draft = compile(service, request, "after-second-answer")
    assert draft.status == "ready"
    with service.repository.transaction() as db:
        prepared = service.repository.load(db, "prepared_sources", request, PreparedSources)
        assert prepared.learning_version == version
    assert not any(
        e.kind == "knowledge_reused" and e.request_id == request for e in learning.state().events
    )
    if stage == "accept":
        quote = service.issue_quote(
            request, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
        )
    learning.transition(
        LearningCommand(idempotency_key="revoke", target_id=version), "controller", "revoke"
    )
    with pytest.raises(DomainError, match="no longer active"):
        if stage == "quote":
            service.issue_quote(
                request, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
            )
        else:
            service.accept_quote(
                AcceptQuoteCommand(
                    quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="accept"
                )
            )


@pytest.mark.parametrize("change", ["expired", "stale"])
def test_obsolete_reviews_remain_history_but_are_not_actionable(live, change):
    from datetime import timedelta

    service, learning = live
    learning.publish(example_bundle(service.clock()), "worker")
    request = create(service, "obsolete-review")
    compile(service, request, "hold")
    if change == "expired":
        service.clock.now += timedelta(minutes=6)
    else:
        learning.publish(example_bundle(service.clock(), 2), "worker")
    reviews = [r for r in learning.state().reviews if r.request_id == request]
    assert len(reviews) == 2
    assert all(not r.actionable and r.review_status == change for r in reviews)


@pytest.mark.parametrize("defect", ["rows", "evidence"])
def test_qualification_rejects_broken_real_composition(live, monkeypatch, defect):
    import json

    from app.agents import source_preparation
    from app.catalog.preparation import PreparedSources
    from app.datasets import canonical

    service, learning = live
    _, candidate = trained(live)
    real = source_preparation.compile_composed_sources
    calls = []

    def broken(engine, encounter_ids, **kwargs):
        draft = real(engine, encounter_ids, **kwargs)
        calls.append(draft.request_id)
        with engine.service.repository.transaction() as db:
            prepared = engine.service.repository.load(
                db, "prepared_sources", draft.request_id, PreparedSources
            )
            sources = list(prepared.sources)
            if defect == "rows":
                index = next(
                    i
                    for i, s in enumerate(sources)
                    if ":prepared:" in s.source_id and s.source_id.endswith(":gym_or_fitness_app")
                )
                raw = json.loads(engine.service.store.read(sources[index].artifact))
                raw["rows"] = raw["rows"][:-1]
                artifact = engine.service.store.put(canonical(raw), "application/json")
                sources[index] = sources[index].model_copy(update={"artifact": artifact})
            else:
                sources = [s for s in sources if not s.source_id.endswith(":schema-lineage")]
            engine.service.repository.put(
                db,
                "prepared_sources",
                draft.request_id,
                prepared.model_copy(update={"sources": tuple(sources)}),
            )
        return draft

    monkeypatch.setattr(source_preparation, "compile_composed_sources", broken)
    result = learning.qualify(
        LearningCommand(idempotency_key="broken-join", target_id=candidate), "controller"
    )
    assert calls, "qualification must execute the production composition adapter"
    assert result.status == "REJECTED"
    assert not learning.state().qualification.passed
