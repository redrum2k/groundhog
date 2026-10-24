"""Jeff-owned R3/R4 release blockers: desired integration behavior, not claimed fixes."""

import pytest

from app.contracts.catalog import ClarifyCommand, RevisionCommand
from app.contracts.runs import RunCreate
from app.orders.runs import Runs


def compile_request(s, run):
    draft = s.get_request(run)
    return s.compile_request(
        run,
        RevisionCommand(
            expected_revision=draft.revision, idempotency_key=f"compile:{draft.revision}"
        ),
    )


@pytest.mark.xfail(
    strict=True, reason="R3 release blocker, Jeff: negated inclusion expands category"
)
def test_negative_yoga_instruction_does_not_expand_scope(dataset_service):
    s, _ = dataset_service
    run = (
        Runs(s)
        .create(
            RunCreate(
                prompt="SF adults 25-34, gym membership or fitness app users. Do not include yoga."
            ),
            "r3",
        )
        .id
    )
    draft = compile_request(s, run)
    assert (
        draft.status == "clarification"
        or draft.specification.terms.category == "gym_or_fitness_app"
    )


@pytest.mark.xfail(
    strict=True,
    reason="R4 release blocker, Jeff: question-bound correction cannot supersede rejected cohort",
)
def test_question_bound_cohort_correction_supersedes_original_text(dataset_service):
    s, _ = dataset_service
    run = (
        Runs(s)
        .create(
            RunCreate(
                prompt="SF adults 18-24, gym membership or fitness app users, grouped by ZIP."
            ),
            "r4",
        )
        .id
    )
    draft = compile_request(s, run)
    assert draft.question.field == "cohort"
    original, deadline = draft.prompt, draft.deadline
    s.clarify(
        run,
        ClarifyCommand(
            expected_revision=draft.revision,
            idempotency_key="correct",
            question_id=draft.question.question_id,
            text=(
                "Yes, change to San Francisco adults 25-34 grouped by ZIP, "
                "gym membership or fitness app use."
            ),
        ),
    )
    corrected = compile_request(s, run)
    assert (
        corrected.prompt == original
        and corrected.deadline == deadline
        and len(corrected.answers) == 1
    )
    assert corrected.status == "ready"
    assert corrected.specification.terms.age_min == 25
