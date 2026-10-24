"""A qualified answer is not unqualified acceptance of the supported offer."""

import pytest

from app.agents.dataset import _affirmative
from app.contracts.catalog import QuoteRequest
from app.orders.catalog import CatalogService
from app.storage.catalog import DomainError
from tests.dataset.test_cohort_ambiguity import PROMPT, AmbiguousCohort
from tests.dataset.test_intake_conversation import ModelIntent, answer, start, use_model


@pytest.mark.parametrize("offline_restart", [False, True])
@pytest.mark.parametrize("reply", ["yes, 65+", "yes, >65", "yes, 94110", "yes, 25–34", "yes, +"])
def test_qualified_answer_cannot_accept_model_cohort_offer(dataset_service, offline_restart, reply):
    service, clock = dataset_service
    fake = AmbiguousCohort()
    use_model(service, fake)
    first = start(service, PROMPT)
    assert first.question and ":cohort_scope_offer:" in first.question.question_id
    if offline_restart:
        service = CatalogService(service.repository, service.store.root, clock)
    final = answer(service, first, reply)
    assert final.status == "human_review" and final.specification is None
    assert final.prompt == first.prompt and final.deadline == first.deadline
    assert final.answers[-1].text == reply and final.questions_asked == 1
    assert len(fake.calls) == (1 if offline_restart else 2)
    with pytest.raises(DomainError):
        service.issue_quote(
            final.request_id,
            QuoteRequest(expected_revision=final.revision, idempotency_key="no-implicit-consent"),
        )


@pytest.mark.parametrize("offline_restart", [False, True])
@pytest.mark.parametrize("reply", ["yes, 65+", "yes, 94110", "yes, 50%"])
def test_numeric_qualifier_does_not_accept_broader_category(
    dataset_service, offline_restart, reply
):
    service, clock = dataset_service
    first = start(service, "SF adults 25-34, gym membership only, counts by ZIP.")
    assert first.question.field == "category_offer_base"
    if offline_restart:
        service = CatalogService(service.repository, service.store.root, clock)
    else:
        use_model(service, ModelIntent("gym_or_fitness_app"))
    final = answer(service, first, reply)
    assert final.status == "human_review" and final.specification is None
    assert final.answers[-1].text == reply and final.deadline == first.deadline
    assert final.questions_asked == first.questions_asked


@pytest.mark.parametrize("reply", ["yes, ６５＋", "yes, ²", "yes, ≤18", "yes, $", "yes?", "yes/no"])
def test_consent_normalization_retains_unrecognized_qualifiers(reply):
    assert not _affirmative(reply)


@pytest.mark.parametrize("reply", [" YES! ", "Yes, please.", "I accept.", "Yes, I accept!"])
def test_plain_affirmative_punctuation_still_works(reply):
    assert _affirmative(reply)
