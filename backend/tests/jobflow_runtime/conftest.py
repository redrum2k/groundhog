import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contracts.jobflow import Command, InvestigationOutcome, OrderCreate, Question
from app.runtime.jobflow import DEMO_ACTORS, Jobflow
from app.runtime.jobflow_worker import drain


class Harness:
    def __init__(self, path):
        self.now = datetime(2026, 10, 23, 12, tzinfo=UTC)
        self.actors = {actor.id: actor for actor in DEMO_ACTORS}
        self.seen = []
        self.service = Jobflow(
            path,
            demo=True,
            clock=lambda: self.now,
            investigator=self.investigate,
            document_extractor=self.parse,
        )

    def parse(self, raw, filename, media_type):
        return {
            "text": raw.decode(),
            "pages": [],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "media_type": media_type,
        }

    async def investigate(self, order, issue_id, *, mode="DETERMINISTIC", **kwargs):
        self.seen.append((order, issue_id, mode, kwargs))
        issue = next(issue for issue in order.issues if issue.id == issue_id)
        answered = any(question.status == "ANSWERED" for question in issue.questions)
        return InvestigationOutcome(
            issue_id=issue_id,
            revision=order.revision,
            findings=[],
            questions=[]
            if answered
            else [
                Question(
                    id=f"question-{uuid4().hex}",
                    issue_id=issue_id,
                    text="Please provide the independently accepted amendment for due_date",
                    recipient="customer",
                )
            ],
            recommendations=["HUMAN_REVIEW"],
            summary="Deterministic test double; no model inference",
            model_mode=mode,
        )

    def create(self, **kwargs):
        return self.service.create(
            self.actors["customer"],
            OrderCreate(
                idempotency_key=f"create-{uuid4().hex}", document_count=3, failed_count=1, **kwargs
            ),
        )

    def get(self, order):
        return self.service.view(self.actors["customer"], order.id)

    def cmd(self, order, role, verb, **kwargs):
        request = Command(
            idempotency_key=kwargs.pop("idempotency_key", uuid4().hex),
            expected_revision=kwargs.pop("expected_revision", self.get(order).revision),
            verb=verb,
            **kwargs,
        )
        return self.service.command(self.actors[role], order.id, request)

    def drain(self):
        asyncio.run(drain(self.service))

    def quote(self, order):
        order = self.get(order)
        action = next(
            action
            for action in reversed(order.actions)
            if action.kind == "QUOTE" and action.status == "PROPOSED"
        )
        order = self.cmd(order, "controller", "approve_action", action_id=action.id)
        order = self.cmd(
            order,
            "executor",
            "execute_action",
            action_id=action.id,
            approval_id=order.approvals[-1].id,
        )
        return order, order.change_orders[-1]


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path / "domain.sqlite3")
