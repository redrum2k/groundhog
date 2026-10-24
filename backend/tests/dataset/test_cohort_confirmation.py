"""A bound yes is consent only to the precise cohort offer actually displayed."""

import json

import pytest

from tests.dataset.test_intake_conversation import ModelIntent, answer, start, use_model


class CohortModel(ModelIntent):
    def parse(self, **kwargs):
        payload = json.loads(kwargs["messages"][0]["content"])
        self.scope = "gym_or_fitness_app"
        self.question = (
            "Only San Francisco adults 25-34 are supported. Would you like that cohort instead?"
            if not payload["draft"]["answers"]
            else None
        )
        response = super().parse(**kwargs)
        response.parsed_output = response.parsed_output.model_copy(
            update={"clarification_field": "cohort"}
        )
        return response


@pytest.mark.parametrize("model", [False, True])
def test_yes_to_explicit_supported_cohort_offer_progresses(dataset_service, model):
    service, _ = dataset_service
    if model:
        use_model(service, CohortModel())
    first = start(service, "SF adults 18-24, gym membership or fitness app use, counts by ZIP.")
    assert first.question.field == "cohort"
    final = answer(service, first, "yes")
    assert final.status == "ready"
    assert final.specification.terms.age_min == 25
    assert final.specification.terms.geography == "San Francisco"
    assert final.prompt == first.prompt and final.deadline == first.deadline


@pytest.mark.parametrize("text", ["no", "yes, but keep adults 18-24", "yes, but use Oakland"])
def test_conditional_or_declined_cohort_is_not_consent(dataset_service, text):
    service, _ = dataset_service
    first = start(service, "SF adults 18-24, gym membership or fitness app use.")
    final = answer(service, first, text)
    assert final.status != "ready" and final.specification is None
    assert final.deadline == first.deadline


def test_yes_to_legacy_open_question_does_not_accept_an_unspecified_cohort(dataset_service):
    service, _ = dataset_service
    first = start(service, "SF adults 18-24, gym membership or fitness app use.")
    old_question = first.question.model_copy(
        update={
            "question_id": first.request_id + ":cohort:1",
            "prompt": "Which cohort do you mean?",
        }
    )
    first = first.model_copy(update={"question": old_question, "question_history": (old_question,)})
    with service.repository.transaction() as db:
        service.repository.put(db, "request", first.request_id, first)
    final = answer(service, first, "yes")
    assert final.status != "ready" and final.specification is None
