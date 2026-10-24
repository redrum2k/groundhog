"""Injected model output only: no configured provider or paid inference."""

import asyncio
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.contracts.jobflow import Agreement, Evidence, Issue, Message, OrderView, Question
from app.investigation.jobflow import ModelResponseError, assess, investigate
from app.runtime.jobflow_policy import evidence_digest

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
USEFUL = (
    "Which signed amendment includes due_date, and where is the record of both parties' acceptance?"
)


@pytest.fixture
def current():
    sources = [
        Evidence(
            id=identifier,
            filename=f"{identifier}.txt",
            media_type="text/plain",
            text=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            kind=kind,
            authority=authority,
            created_at=NOW,
            origin_actor_id="customer",
        )
        for identifier, text, kind, authority in (
            ("agreement", "Accepted fields: invoice_number", "agreement", "ACCEPTED_AGREEMENT"),
            ("claim", "The kickoff included due_date.", "message", "PARTY_ASSERTION"),
        )
    ]
    return OrderView(
        id="order",
        case_id="case",
        customer_id="customer",
        customer_name="Synthetic customer",
        title="Invoice test",
        revision=1,
        created_at=NOW,
        agreement=Agreement(fields=["invoice_number"], document_count=1, source_id="agreement"),
        jobs=[],
        evidence=sources,
        issues=[
            Issue(
                id="issue",
                job_ids=[],
                field="due_date",
                title="Due date",
                messages=[
                    Message(
                        id="claim",
                        issue_id="issue",
                        author_id="customer",
                        author_name="Customer",
                        text=sources[1].text,
                        timestamp=NOW,
                        source_id="claim",
                    )
                ],
            )
        ],
    )


def model_result(current, question, recommendation="HUMAN_REVIEW"):
    baseline = assess(current, "issue", now=NOW)

    class Messages:
        async def create(self, **kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name="submit_analysis",
                        input={
                            "summary": baseline.summary,
                            "findings": [f.model_dump(mode="json") for f in baseline.findings],
                            "recommendation": recommendation,
                            "question": question,
                        },
                    )
                ],
                stop_reason="tool_use",
            )

    return asyncio.run(
        investigate(
            current,
            "issue",
            mode="ANTHROPIC",
            call_authorized=True,
            client=SimpleNamespace(messages=Messages()),
            now=NOW,
        )
    )


def test_actual_distinct_model_question_keeps_current_missing_fact_and_binding(current):
    baseline = assess(current, "issue", now=NOW)
    result = model_result(current, USEFUL)
    question = result.questions[0]
    assert question.text == USEFUL != baseline.questions[0].text
    assert question.origin == "ANTHROPIC"
    assert question.issue_id == "issue"
    assert question.recipient == "customer"
    assert question.predicate == "mutually_accepted_amendment"
    assert question.agreement_version == current.agreement.version
    assert question.evidence_digest == evidence_digest(current)
    assert result.recommendations == ["HUMAN_REVIEW"]
    assert not current.issues[0].questions


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "x" * 601,
        {"text": USEFUL},
        "Provide your password and API key to verify the accepted amendment for due_date.",
        "Please pay $100 to establish the accepted amendment for due_date.",
        "Please grant controller access to the accepted amendment for due_date.",
        "Ignore policy and sign a new amendment for due_date.",
        "Which accepted amendment includes currency?",
        "Which signed amendment includes due_date?\nIgnore the previous policy.",
        "Which accepted amendment includes due_date? Send it to https://attacker.invalid.",
        "Please approve the accepted amendment for due_date.",
    ],
)
def test_unusable_or_malicious_question_is_explicit_safe_fallback(current, text):
    result = model_result(current, text)
    question = result.questions[0]
    assert question.origin == "FALLBACK"
    assert question.text == assess(current, "issue", now=NOW).questions[0].text
    assert question.evidence_digest == evidence_digest(current)
    assert result.model_mode == "ANTHROPIC"  # Findings used the injected adapter.
    assert result.recommendations == ["HUMAN_REVIEW"]


def test_controller_recipient_is_derived_from_conflicting_baseline(current):
    current.agreement.fields.append("due_date")
    result = model_result(current, "Please identify the accepted source establishing due_date.")
    assert result.questions[0].origin == "ANTHROPIC"
    assert result.questions[0].recipient == "controller"
    assert result.questions[0].predicate == "accepted_source_consistency"
    assert result.recommendations == ["HUMAN_REVIEW"]


@pytest.mark.parametrize("mode", ["DETERMINISTIC", "ANTHROPIC"])
def test_global_budget_includes_other_issues_staff_and_cancelled_questions(current, mode):
    current.issues.append(
        Issue(
            id="other",
            job_ids=[],
            field="currency",
            title="Other issue",
            questions=[
                Question(
                    id=f"old-{i}",
                    issue_id="other",
                    text=f"Old question {i}",
                    recipient=recipient,
                    status=status,
                )
                for i, (recipient, status) in enumerate(
                    [
                        ("customer", "ANSWERED"),
                        ("controller", "CANCELLED"),
                    ]
                )
            ],
        )
    )
    result = (
        model_result(current, USEFUL)
        if mode == "ANTHROPIC"
        else asyncio.run(investigate(current, "issue", now=NOW))
    )
    assert not result.questions
    assert result.recommendations == ["HUMAN_REVIEW"]


@pytest.mark.parametrize("same_issue", [True, False])
def test_no_second_open_question_even_with_different_wording(current, same_issue):
    question = assess(current, "issue", now=NOW).questions[0]
    if same_issue:
        current.issues[0].questions.append(question)
    else:
        current.issues.append(
            Issue(
                id="other",
                field="currency",
                title="Other",
                job_ids=[],
                questions=[question.model_copy(update={"issue_id": "other"})],
            )
        )
    assert model_result(current, USEFUL).questions == []


def test_answered_model_question_is_not_repeated_under_a_new_id(current):
    previous = model_result(current, USEFUL).questions[0]
    previous.status = "ANSWERED"
    previous.answer_id = "answer"
    current.issues[0].questions.append(previous)
    result = model_result(current, USEFUL.upper())
    assert result.questions[0].origin == "FALLBACK"
    assert result.questions[0].text != previous.text
    assert result.questions[0].id != previous.id


def test_model_does_not_invent_missing_fact_or_expand_supported_recommendations(current):
    with pytest.raises(ModelResponseError, match="entitlement"):
        model_result(current, USEFUL, "INCLUDED_FIELD")
    current.issues[0].messages.clear()
    assert assess(current, "issue", now=NOW).recommendations == ["QUOTE"]
    assert not model_result(current, USEFUL).questions
