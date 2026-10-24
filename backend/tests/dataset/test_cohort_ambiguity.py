"""Greptile P1: model-detected material scope cannot disappear in partial parsing."""

import json

import pytest

from app.contracts.catalog import ClarifyCommand, QuoteRequest, RevisionCommand
from app.orders.catalog import CatalogService
from app.storage.catalog import DomainError
from tests.dataset.test_intake_conversation import ModelIntent, answer, start, use_model


class AmbiguousCohort(ModelIntent):
    def __init__(self, question="Would you accept San Francisco only?"):
        super().__init__("ambiguous", question=question)

    def parse(self, **kwargs):
        payload = json.loads(kwargs["messages"][0]["content"])
        # Deliberately overconfident on ANY answer: consent must not rely on this.
        if payload["draft"]["answers"]:
            self.scope, self.question = "gym_or_fitness_app", None
        response = super().parse(**kwargs)
        response.parsed_output = response.parsed_output.model_copy(
            update={"clarification_field": "cohort"}
        )
        return response


PROMPT = "SF and Seattle adults 25-34, gym membership or fitness app use, counts by ZIP."


@pytest.mark.parametrize("question", ["Would you accept San Francisco only?", None])
@pytest.mark.parametrize("prompt", [PROMPT, PROMPT.replace("and Seattle", "and retirees")])
def test_material_cohort_ambiguity_blocks_partial_parse(dataset_service, question, prompt):
    service, _ = dataset_service
    use_model(service, AmbiguousCohort(question))
    draft = start(service, prompt)
    assert draft.status == "clarification" and draft.specification is None
    assert draft.question.field == "cohort"
    assert "25–34 in San Francisco" in draft.question.prompt
    assert draft.questions_asked == 1
    with pytest.raises(DomainError):
        service.issue_quote(
            draft.request_id,
            QuoteRequest(expected_revision=draft.revision, idempotency_key="bypass-quote"),
        )


@pytest.mark.parametrize(
    "reply,ready",
    [
        ("yes", True),
        ("no", False),
        ("maybe", False),
        ("yes, and Seattle too", False),
        ("SF and Seattle adults 25-34", False),
        ("yes, but include retirees", False),
    ],
)
def test_only_bound_consent_resolves_model_cohort_offer(dataset_service, reply, ready):
    service, clock = dataset_service
    fake = AmbiguousCohort()
    use_model(service, fake)
    first = start(service, PROMPT)
    assert first.question is not None
    # Restart on the same persisted history; an offline compiler must retain the gate.
    restarted = CatalogService(service.repository, service.store.root, clock)
    final = answer(restarted, first, reply)
    assert (final.status == "ready") == ready
    assert final.prompt == first.prompt and final.deadline == first.deadline
    assert final.questions_asked <= 2 and len(final.answers) == 1
    if ready:
        assert final.specification.terms.geography == "San Francisco"
        assert final.specification.terms.age_min == 25
    else:
        assert final.specification is None


def test_model_cohort_offer_replay_wrong_question_and_budget(dataset_service):
    service, _ = dataset_service
    fake = AmbiguousCohort()
    use_model(service, fake)
    first = start(service, PROMPT)
    assert first.question is not None
    source_revision = fake.calls[0]["draft"]["revision"] - 1
    replay = service.compile_request(
        first.request_id,
        RevisionCommand(
            expected_revision=source_revision, idempotency_key=f"compile:{source_revision}"
        ),
    )
    assert replay == first and len(fake.calls) == 1
    with pytest.raises(DomainError):
        service.clarify(
            first.request_id,
            ClarifyCommand(
                expected_revision=first.revision,
                idempotency_key="wrong",
                question_id=first.request_id + ":category:1",
                text="yes",
            ),
        )
    final = answer(service, first, "yes")
    assert final.status == "ready" and final.questions_asked == 1
    assert len(fake.calls) == 2
    assert final.deadline == first.deadline
