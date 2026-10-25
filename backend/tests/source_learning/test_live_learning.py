import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.brokerage_acceptance import Clock, fund
from tools.learning_examples import example_bundle

from app.contracts.catalog import AcceptQuoteCommand, QuoteRequest, RevisionCommand
from app.contracts.runs import RunCreate
from app.contracts.source_learning import LearningCommand, ResolveSource
from app.learning.service import OWNER, SourceLearning
from app.main import create_app
from app.orders.catalog import CatalogService
from app.orders.runs import Runs
from app.orders.service import DomainError
from app.storage.catalog import CatalogRepository


@pytest.fixture
def live(tmp_path):
    service = CatalogService(CatalogRepository(tmp_path / "orders.db"), tmp_path / "bytes", Clock())
    learning = SourceLearning(service, enabled=True)
    service.source_learning = learning
    return service, learning


def create(service, key):
    return (
        Runs(service)
        .create(
            RunCreate(
                prompt="SF adults 25-34, gym membership or fitness app use, counts by ZIP.",
                corpus_id="sf-aggregate-v1",
            ),
            key,
        )
        .id
    )


def compile(service, request_id, key):
    draft = service.get_request(request_id)
    return service.compile_request(
        request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key=key)
    )


def trained(live):
    service, learning = live
    bundle = learning.publish(example_bundle(service.clock()), "provider:local-worker")
    request_id = create(service, "training-order")
    assert compile(service, request_id, "compile-1").status == "human_review"
    reviews = learning.state().reviews
    assert len(reviews) == 2
    for review, column in zip(reviews, ("v_count", "p_adults"), strict=True):
        learning.resolve(
            ResolveSource(
                idempotency_key="resolve-" + column,
                encounter_id=review.encounter_id,
                column=column,
                explanation="Simulated owner confirms this partition's unique-adult count column.",
            ),
            OWNER,
        )
    draft = compile(service, request_id, "after-owner")
    assert draft.status == "ready", draft.error
    candidate = learning.propose(
        LearningCommand(idempotency_key="propose", target_id=bundle.record_id),
        "provider:local-worker",
    )
    return request_id, candidate.record_id


def test_full_cycle_active_reuse_restart_and_conflict(live):
    service, learning = live
    first, candidate = trained(live)
    assert learning.state().active_version is None
    with pytest.raises(DomainError, match="qualification"):
        learning.transition(
            LearningCommand(idempotency_key="early", target_id=candidate), "controller", "approve"
        )
    report = learning.qualify(
        LearningCommand(idempotency_key="qualify", target_id=candidate), "controller"
    )
    assert report.status == "QUALIFIED"
    state = learning.state()
    assert state.qualification.correct_both == 6
    assert state.qualification.candidate_reviews < state.qualification.baseline_reviews
    approved = learning.transition(
        LearningCommand(idempotency_key="approve", target_id=candidate), "controller", "approve"
    )
    learning.transition(
        LearningCommand(idempotency_key="activate", target_id=approved.record_id),
        "controller",
        "activate",
    )
    service = CatalogService(service.repository, service.store.root, service.clock)
    learning = SourceLearning(service, enabled=True)
    service.source_learning = learning
    assert learning.state().active_version == approved.record_id
    learning.publish(example_bundle(service.clock(), 2), "provider:local-worker")
    later = create(service, "different-new-order")
    draft = compile(service, later, "automatic")
    assert draft.status == "ready" and later != first
    assert not [r for r in learning.state().reviews if r.request_id == later]
    quote = service.issue_quote(
        later, QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
    )
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="AcmeFitness", idempotency_key="accept"
        )
    )
    assert order.authorization.status == "pending" and not order.deliveries
    assert fund(service, order).verification.passed
    learning.publish(example_bundle(service.clock(), 3, conflict=True), "provider:local-worker")
    blocked = create(service, "authority-conflict")
    assert compile(service, blocked, "conflict").status == "human_review"
    assert all(
        r.reason == "authority_conflict"
        for r in learning.state().reviews
        if r.request_id == blocked
    )


def test_unapproved_history_does_not_automatically_activate(live):
    service, learning = live
    trained(live)
    learning.publish(example_bundle(service.clock(), 2), "provider:local-worker")
    later = create(service, "unapproved-future")
    assert compile(service, later, "future").status == "human_review"


def test_route_authority_and_disabled_mode(tmp_path):
    with TestClient(
        create_app(
            tmp_path / "disabled.db",
            artifact_root=tmp_path / "disabled",
            run_worker=False,
            internal_token="worker",
            reviewer_token="controller",
        )
    ) as client:
        assert (
            client.get("/source-learning/state", headers={"X-Internal-Token": "worker"}).status_code
            == 503
        )
    with TestClient(
        create_app(
            tmp_path / "enabled.db",
            artifact_root=tmp_path / "enabled",
            run_worker=False,
            source_learning=True,
            internal_token="worker",
            reviewer_token="controller",
            source_owner_token="owner",
        )
    ) as client:
        assert client.get("/source-learning/state").status_code == 403
        assert client.get("/source-learning/state", headers={"X-Internal-Token": "worker"}).json()[
            "enabled"
        ]
        payload = {"idempotency_key": "no", "target_id": "not-a-version"}
        assert (
            client.post(
                "/source-learning/activate", json=payload, headers={"X-Internal-Token": "worker"}
            ).status_code
            == 403
        )
