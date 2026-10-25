"""Malformed clarification wording gets one counted repair, never implicit consent."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.agents.bounded_client import BoundedClient
from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import RequestDraft, RevisionCommand
from app.contracts.dataset_intake import DatasetClarification, DatasetIntakeProposal
from app.contracts.runs import RunCreate
from app.orders.runs import Runs
from app.orders.service import DomainError
from tests.dataset.test_intake_conversation import ModelIntent, answer
from tests.investigation.test_model_budget import budget


class RepairIntent(ModelIntent):
    def __init__(
        self, repair="Should fitness include standalone yoga in addition to gym or fitness-app use?"
    ):
        super().__init__(question="Should fitness mean gym or app use? Should it include yoga?")
        self.repair = repair
        self.after_proposal = lambda: None

    def parse(self, **kwargs):
        if kwargs["output_format"] is DatasetClarification:
            self.calls.append(json.loads(kwargs["messages"][0]["content"]))
            return SimpleNamespace(
                stop_reason="end_turn",
                usage={"input_tokens": 100, "output_tokens": 20},
                parsed_output=DatasetClarification(clarification=self.repair),
            )
        result = super().parse(**kwargs)
        self.after_proposal()
        return result


def prepare(service, tmp_path, fake, *, previous_calls=0, prompt=None):
    ledger = budget(tmp_path)
    service.dataset_compiler = ClaudeGateway(
        enabled=True,
        model="claude-opus-5-5",
        client=BoundedClient(client=SimpleNamespace(messages=fake), budget=ledger),
    )
    run = Runs(service).create(RunCreate(**({"prompt": prompt} if prompt else {})), "repair").id
    original = service.get_request(run)
    with service.repository.transaction() as db:
        draft = original.model_copy(update={"compiler_calls": previous_calls})
        service.repository.put(db, "request", run, draft)
    command = RevisionCommand(expected_revision=draft.revision, idempotency_key="compile")
    return run, original, command, ledger


def test_repair_counts_calls_preserves_intent_deadline_and_replay(dataset_service, tmp_path):
    service, _ = dataset_service
    fake = RepairIntent()
    run, original, command, ledger = prepare(service, tmp_path, fake)
    draft = service.compile_request(run, command)
    assert draft.status == "clarification" and draft.error is None
    assert draft.question.prompt == fake.repair and draft.questions_asked == 1
    assert draft.specification is None and draft.deadline == original.deadline
    assert draft.compiler_calls == len(fake.calls) == ledger.summary()["requests_used"] == 2
    assert service.compile_request(run, command) == draft
    assert len(fake.calls) == 2  # Exact replay never buys another wording repair.
    with service.repository.transaction() as db:
        rejected = service.repository.load(db, "dataset_intake", f"{run}:2", DatasetIntakeProposal)
        repaired = service.repository.load(db, "dataset_intake", f"{run}:3", DatasetIntakeProposal)
    assert rejected.clarification == fake.question
    assert rejected.model_dump(exclude={"clarification"}) == repaired.model_dump(
        exclude={"clarification"}
    )
    fake.scope, fake.question = "gym_or_fitness_app", None
    final = answer(service, draft, "Gym membership or fitness-app use, excluding yoga.")
    assert final.status == "ready" and final.specification.terms.category == "gym_or_fitness_app"
    assert final.deadline == original.deadline and final.compiler_calls == 3


def test_invalid_repair_stops_without_terms_or_more_calls(dataset_service, tmp_path):
    service, _ = dataset_service
    fake = RepairIntent("Which scope? Also what price?")
    run, _, command, ledger = prepare(service, tmp_path, fake)
    draft = service.compile_request(run, command)
    assert draft.status == "human_review" and draft.specification is None
    assert draft.question is None and draft.questions_asked == 0
    assert "after retrying" in draft.error
    assert draft.compiler_calls == len(fake.calls) == ledger.summary()["requests_used"] == 2


def test_repair_cannot_exceed_four_reserved_compiler_calls(dataset_service, tmp_path):
    service, _ = dataset_service
    fake = RepairIntent()
    run, _, command, ledger = prepare(service, tmp_path, fake, previous_calls=3)
    draft = service.compile_request(run, command)
    assert draft.status == "human_review" and draft.specification is None
    assert draft.compiler_calls == 4 and "budget exhausted" in draft.error
    assert len(fake.calls) == ledger.summary()["requests_used"] == 1
    with service.repository.transaction() as db:
        rejected = service.repository.load(db, "dataset_intake", f"{run}:2", DatasetIntakeProposal)
    assert rejected.clarification == fake.question


@pytest.mark.parametrize("change", ["expired", "stale"])
def test_repair_never_dispatches_for_expired_or_changed_draft(dataset_service, tmp_path, change):
    service, clock = dataset_service
    fake = RepairIntent()
    run, original, command, ledger = prepare(service, tmp_path, fake)

    def change_draft():
        if change == "expired":
            clock.advance(301)
        else:
            with service.repository.transaction() as db:
                current = service.repository.load(db, "request", run, RequestDraft)
                current.revision += 1
                service.repository.put(db, "request", run, current)

    fake.after_proposal = change_draft
    with pytest.raises(DomainError, match="stale compiler result"):
        service.compile_request(run, command)
    assert len(fake.calls) == ledger.summary()["requests_used"] == 1
    assert service.get_request(run).deadline == original.deadline


def test_repair_obeys_shared_spending_window(dataset_service, tmp_path):
    service, _ = dataset_service
    fake = RepairIntent()
    run, _, command, ledger = prepare(service, tmp_path, fake)
    fake.after_proposal = lambda: setattr(
        ledger, "cutoff", datetime.now(UTC) - timedelta(seconds=1)
    )
    draft = service.compile_request(run, command)
    assert draft.status == "human_review" and draft.specification is None
    assert "authorization denied" in draft.error
    assert len(fake.calls) == ledger.summary()["requests_used"] == 1


def test_repair_cannot_turn_model_detected_ambiguity_into_consent(dataset_service, tmp_path):
    service, _ = dataset_service
    fake = RepairIntent(
        "Should the combined gym-or-fitness-app group be limited to active subscriptions?"
    )
    run, _, command, _ = prepare(
        service,
        tmp_path,
        fake,
        prompt="SF adults 25-34, gym or fitness app users with current subscriptions.",
    )
    draft = service.compile_request(run, command)
    assert draft.status == "clarification" and draft.specification is None
    assert draft.question.prompt == fake.repair
