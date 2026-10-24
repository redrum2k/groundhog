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


@pytest.mark.parametrize(
    "instruction,category",
    [
        ("Include yoga.", "gym_app_or_yoga"),
        ("Do not include yoga.", "gym_or_fitness_app"),
        ("Don't include yoga.", "gym_or_fitness_app"),
        ("Exclude yoga.", "gym_or_fitness_app"),
        ("Without yoga.", "gym_or_fitness_app"),
        ("Include yoga and do not include yoga.", None),
        ("Include yoga but exclude yoga.", None),
        ("Do not exclude yoga.", None),
        ("Not only yoga.", None),
    ],
)
def test_category_polarity_not_substring_matching(dataset_service, instruction, category):
    s, _ = dataset_service
    run = (
        Runs(s)
        .create(
            RunCreate(
                prompt="SF adults 25-34, gym membership or fitness app users. " + instruction
            ),
            "polarity",
        )
        .id
    )
    draft = compile_request(s, run)
    if category is None:
        assert draft.status == "clarification" and draft.question.field == "category"
    else:
        assert draft.status == "ready" and draft.specification.terms.category == category


@pytest.mark.parametrize(
    "initial,answer,ready",
    [
        ("Oakland adults 25-34", "Change to San Francisco adults 25-34.", True),
        ("SF adults 18-24", "Use SF adults 25-34 or 18-24.", False),
        ("SF adults 18-24", "Use adults 25-34 in SF or Oakland.", False),
        ("SF adults 18-24", "Not adults 18-24 but SF adults 25-34.", True),
        ("SF adults 18-24", "No, keep adults 18-24 in SF.", False),
    ],
)
def test_bound_correction_and_contradictions_preserve_history(
    dataset_service, initial, answer, ready
):
    s, _ = dataset_service
    run = (
        Runs(s)
        .create(RunCreate(prompt=initial + ", gym membership or fitness app users."), "correction")
        .id
    )
    draft = compile_request(s, run)
    original, deadline = draft.prompt, draft.deadline
    s.clarify(
        run,
        ClarifyCommand(
            expected_revision=draft.revision,
            idempotency_key="answer",
            question_id=draft.question.question_id,
            text=answer,
        ),
    )
    corrected = compile_request(s, run)
    assert corrected.prompt == original and corrected.deadline == deadline
    assert corrected.answers[0].text == answer and len(corrected.answers) == 1
    assert corrected.questions_asked == (1 if ready else 2)
    assert (corrected.status == "ready") == ready
