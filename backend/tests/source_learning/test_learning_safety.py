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
