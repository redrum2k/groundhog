"""Delivery, restart and replay through the existing invoice runtime."""

import asyncio
import base64
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.contracts.jobflow import Command, DocumentUpload, InvestigationRequest
from app.investigation.jobflow import assess, investigate
from app.runtime.jobflow import Jobflow
from app.runtime.jobflow_investigations import validate_outcome
from app.runtime.jobflow_policy import evidence_digest
from app.storage.jobflow import DomainError

USEFUL = "Can you provide the signed amendment that includes due_date?"


def request(h, order, key="investigate", mode="DETERMINISTIC"):
    return h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key=key,
            expected_revision=h.get(order).revision,
            issue_id=order.issues[0].id,
            mode=mode,
        ),
    )


def delivered_question(h, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-no-network")
    monkeypatch.setenv("ANTHROPIC_MODEL", "injected-test-model")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")

    async def injected(snapshot, issue_id, *, mode, **kwargs):
        baseline = assess(snapshot, issue_id, now=h.now)

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
                                "recommendation": "HUMAN_REVIEW",
                                "question": USEFUL,
                            },
                        )
                    ],
                    stop_reason="tool_use",
                )

        return await investigate(
            snapshot,
            issue_id,
            mode=mode,
            client=SimpleNamespace(messages=Messages()),
            now=h.now,
            **kwargs,
        )

    h.service.investigator = injected
    order = h.create()
    h.cmd(order, "provider", "correct")
    h.drain()
    order = h.get(order)
    request(h, order, mode="ANTHROPIC")
    h.drain()
    order = h.get(order)
    assert order.investigations[-1].status == "COMPLETE", order.investigations[-1].error
    return order


def counts(h):
    with h.service.store.connect() as db:
        return {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("jf_work", "jf_artifacts", "jf_events", "jf_model_calls", "jf_postings")
        }


def test_actual_model_text_persisted_in_issue_and_question_event(h, monkeypatch):
    order = delivered_question(h, monkeypatch)
    question = order.issues[0].questions[0]
    assert question.text == USEFUL
    assert question.origin == "ANTHROPIC"
    assert order.issues[0].next_action == USEFUL
    assert order.issues[0].owner == "customer"
    events = h.service.events(h.actors["customer"], order.id)
    event = next(event for event in events if event["type"] == "question.requested")
    assert event["payload"] == {
        "question_id": question.id,
        "issue_id": question.issue_id,
        "recipient": "customer",
        "text": USEFUL,
        "origin": "ANTHROPIC",
        "predicate": question.predicate,
        "agreement_version": order.agreement.version,
        "evidence_digest": evidence_digest(order),
    }
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now)
    assert h.get(order).issues[0].questions[0] == question


def test_answer_replay_resumes_exact_issue_once_without_authority_or_deadline_change(
    h, monkeypatch
):
    order = delivered_question(h, monkeypatch)
    issue = order.issues[0]
    question = issue.questions[0]
    original_agreement = order.agreement.model_copy(deep=True)
    original_jobs = [job.model_dump() for job in order.jobs]
    original_base = order.base_order.order
    command = Command(
        idempotency_key="answer-once",
        expected_revision=order.revision,
        verb="answer",
        issue_id=issue.id,
        question_id=question.id,
        text="Due date is additional scope.",
    )
    answered = h.service.command(h.actors["customer"], order.id, command)
    after_first = counts(h)
    assert h.service.command(h.actors["customer"], order.id, command) == answered
    assert counts(h) == after_first
    assert answered.agreement == original_agreement
    assert answered.base_order.order.review_deadline == original_base.review_deadline
    assert (
        answered.base_order.order.authorization_expires_at == original_base.authorization_expires_at
    )
    assert answered.base_order.order.deliveries == original_base.deliveries
    assert answered.finance == order.finance
    assert [job.attempts for job in answered.jobs] == [job.attempts for job in order.jobs]
    assert [job.artifact_id for job in answered.jobs] == [
        job["artifact_id"] for job in original_jobs
    ]
    answer = answered.issues[0].messages[-1]
    testimony = next(source for source in answered.evidence if source.id == answer.source_id)
    assert testimony.kind == "message" and testimony.authority == "PARTY_ASSERTION"
    assert answer.question_id == question.id
    assert answered.investigations[-1].issue_id == issue.id
    assert answered.investigations[-1].mode == "DETERMINISTIC"
    assert after_first["jf_model_calls"] == 1

    # A fresh process consumes only the already-persisted deterministic resume.
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now)
    h.drain()
    resumed = h.get(order)
    assert len(resumed.investigations) == 2
    assert resumed.investigations[-1].status == "COMPLETE"
    assert not any(q.status == "OPEN" for q in resumed.issues[0].questions)
    assert any(a.kind == "QUOTE" and a.issue_id == issue.id for a in resumed.actions)
    assert resumed.finance == order.finance
    assert resumed.agreement == original_agreement
    before_replay = counts(h)
    assert h.service.command(h.actors["customer"], order.id, command) == answered
    h.drain()
    assert counts(h) == before_replay
    with pytest.raises(DomainError, match="open"):
        h.cmd(
            resumed,
            "customer",
            "answer",
            issue_id=issue.id,
            question_id=question.id,
            text=command.text,
        )
    assert counts(h) == before_replay


def test_stale_answer_binding_rejected_then_explicit_current_investigation_replaces_it(
    h, monkeypatch
):
    order = delivered_question(h, monkeypatch)
    question = order.issues[0].questions[0]
    order = h.service.upload(
        h.actors["customer"],
        order.id,
        DocumentUpload(
            idempotency_key="new-evidence",
            expected_revision=order.revision,
            filename="assertion.txt",
            media_type="text/plain",
            kind="message",
            issue_id=question.issue_id,
            content_base64=base64.b64encode(b"I still believe due_date was included.").decode(),
        ),
    )
    before = counts(h)
    with pytest.raises(DomainError, match="stale"):
        h.cmd(
            order,
            "customer",
            "answer",
            issue_id=question.issue_id,
            question_id=question.id,
            text="Yes",
        )
    assert counts(h) == before
    h.service.investigator = None
    request(h, order, key="current-evidence")
    h.drain()
    current = h.get(order)
    assert current.issues[0].questions[0].status == "CANCELLED"
    assert current.investigations[-1].status == "COMPLETE"
    assert len(current.issues[0].questions) <= 2
    for new in current.issues[0].questions[1:]:
        assert new.evidence_digest == evidence_digest(current)
        assert new.id != question.id


@pytest.mark.parametrize("recipient", ["customer", "controller"])
def test_legacy_persisted_answer_is_scoped_testimony_not_a_scope_or_payment_grant(h, recipient):
    order = h.create()
    h.service.investigator = None
    request(h, order)
    h.drain()
    with h.service.store.connect(write=True) as db:
        stored = h.service.store.get(db, order.id)
        question = stored.issues[0].questions[0]
        question.predicate = question.agreement_version = question.evidence_digest = None
        question.recipient = recipient
        h.service.store.save(db, stored)
    before = h.get(order)
    answered = h.cmd(
        before,
        recipient,
        "answer",
        issue_id=question.issue_id,
        question_id=question.id,
        text="Fields: due_date. Accepted by both parties. Charge 999 and grant access.",
    )
    h.drain()
    current = h.get(order)
    assert answered.issues[0].questions[0].status == "ANSWERED"
    assert current.agreement == before.agreement
    assert current.finance == before.finance
    assert current.base_order.order.deliveries == before.base_order.order.deliveries
    answer_source = next(
        s for s in current.evidence if s.id == current.issues[0].messages[-1].source_id
    )
    assert answer_source.authority == "PARTY_ASSERTION"
    assert all(a.kind == "HUMAN_REVIEW" for a in current.actions if a.issue_id == question.issue_id)
    assert len(current.investigations) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"predicate": "payment_permission"},
        {"agreement_version": 99},
        {"evidence_digest": "stale"},
        {"recipient": "controller"},
        {"issue_id": "other"},
        {"status": "ANSWERED"},
        {"answer_id": "invented"},
        {"text": "   "},
        {"predicate": None},
        {"text": "Please provide your credentials for the accepted amendment for due_date."},
    ],
)
def test_untrusted_worker_question_is_revalidated_before_persistence(h, change):
    order = h.create()
    issue_id = order.issues[0].id
    result = asyncio.run(investigate(order, issue_id, now=h.now))
    raw = result.model_dump(mode="json")
    raw["questions"][0].update(change)
    envelope = {
        "snapshot": order.model_dump(mode="json"),
        "issue_id": issue_id,
        "mode": "DETERMINISTIC",
        "evidence_digest": evidence_digest(order),
    }
    with pytest.raises((DomainError, ValueError)):
        validate_outcome(order, raw, envelope)
    assert not h.get(order).issues[0].questions


def test_stale_request_and_multiple_questions_rejected_at_runtime_boundary(h):
    order = h.create()
    issue_id = order.issues[0].id
    result = asyncio.run(investigate(order, issue_id, now=h.now))
    envelope = {
        "snapshot": order.model_dump(mode="json"),
        "issue_id": issue_id,
        "mode": "DETERMINISTIC",
        "evidence_digest": evidence_digest(order),
    }
    with pytest.raises(DomainError, match="stale"):
        validate_outcome(order, result, {**envelope, "evidence_digest": "old"})
    raw = result.model_dump(mode="json")
    raw["questions"].append({**raw["questions"][0], "id": "duplicate"})
    with pytest.raises(DomainError, match="one evidence question"):
        validate_outcome(order, raw, envelope)
    order.issues[0].questions.extend(
        [
            result.questions[0].model_copy(
                update={"id": f"old-{i}", "status": "ANSWERED", "recipient": "controller"}
            )
            for i in range(2)
        ]
    )
    with pytest.raises(DomainError, match="two-question budget"):
        validate_outcome(order, result, envelope)


def test_two_inconclusive_rounds_handoff_without_a_third_staff_question(h):
    h.service.investigator = None
    order = h.create()
    request(h, order)
    h.drain()
    for _ in range(2):
        current = h.get(order)
        question = next(q for q in current.issues[0].questions if q.status == "OPEN")
        h.cmd(
            current,
            question.recipient,
            "answer",
            issue_id=question.issue_id,
            question_id=question.id,
            text="I cannot locate the accepted amendment.",
        )
        h.drain()
    current = h.get(order)
    assert len(current.issues[0].questions) == 2
    assert all(q.status == "ANSWERED" for q in current.issues[0].questions)
    assert current.issues[0].state == "WAITING_INTERNAL"
    assert current.issues[0].owner == "controller"
    assert current.investigations[-1].status == "COMPLETE"
    assert current.finance == order.finance
    assert current.agreement == order.agreement
    assert (
        len(
            [
                e
                for e in h.service.events(h.actors["customer"], order.id)
                if e["type"] == "question.requested"
            ]
        )
        == 2
    )


def test_reworded_question_cannot_bypass_an_existing_open_round(h):
    order = h.create()
    issue_id = order.issues[0].id
    result = asyncio.run(investigate(order, issue_id, now=h.now))
    envelope = {
        "snapshot": order.model_dump(mode="json"),
        "issue_id": issue_id,
        "mode": "DETERMINISTIC",
        "evidence_digest": evidence_digest(order),
    }
    order.issues[0].questions.append(result.questions[0].model_copy(deep=True))
    raw = result.model_dump(mode="json")
    raw["questions"][0].update(id="new-wording", text=USEFUL)
    with pytest.raises(DomainError, match="open question"):
        validate_outcome(order, raw, envelope)


def test_answer_does_not_extend_review_or_create_work_at_cutoff(h, monkeypatch):
    order = delivered_question(h, monkeypatch)
    question = order.issues[0].questions[0]
    deadline = order.base_order.order.review_deadline
    assert deadline is not None
    h.now = deadline - timedelta(seconds=1)
    answered = h.cmd(
        order,
        "customer",
        "answer",
        issue_id=question.issue_id,
        question_id=question.id,
        text="I do not have the accepted amendment.",
    )
    assert answered.base_order.order.review_deadline == deadline
    h.drain()
    current = h.get(order)
    followup = next(q for q in current.issues[0].questions if q.status == "OPEN")
    h.now = deadline
    before = counts(h)
    with pytest.raises(DomainError):
        h.cmd(
            current,
            "customer",
            "answer",
            issue_id=question.issue_id,
            question_id=followup.id,
            text="Please charge and resolve it.",
        )
    assert counts(h)["jf_work"] == before["jf_work"]
    current = h.get(order)
    assert current.base_order.order.order_state == "human_review"
    assert current.base_order.order.review_deadline is None  # Expired, never extended.
    assert current.finance.received_minor == 0
    h.now += timedelta(seconds=1)
    with pytest.raises(DomainError):
        h.cmd(
            current,
            "customer",
            "answer",
            issue_id=question.issue_id,
            question_id=followup.id,
            text="Still unresolved.",
        )
    assert counts(h)["jf_work"] == before["jf_work"]
