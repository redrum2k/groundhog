import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contracts.jobflow import Command, InvestigationRequest, OrderCreate
from app.runtime.jobflow import DEMO_ACTORS, Jobflow
from app.runtime.jobflow_worker import drain


class Flow:
    def __init__(self, path):
        self.now = datetime.now(UTC)
        self.service = Jobflow(path, demo=True, clock=lambda: self.now)
        self.actors = {a.id: a for a in DEMO_ACTORS}

    def create(self, **kw):
        return self.service.create(
            self.actors["customer"],
            OrderCreate(
                idempotency_key=uuid4().hex,
                document_count=3,
                failed_count=kw.pop("failed_count", 1),
                **kw,
            ),
        )

    def view(self, order):
        return self.service.view(self.actors["customer"], order.id)

    def command(self, order, actor, verb, **kw):
        return self.service.command(
            self.actors[actor],
            order.id,
            Command(
                idempotency_key=uuid4().hex,
                expected_revision=self.view(order).revision,
                verb=verb,
                **kw,
            ),
        )

    def run(self):
        asyncio.run(drain(self.service))

    def investigate(self, order):
        current = self.view(order)
        self.service.investigate(
            self.actors["investigator"],
            order.id,
            InvestigationRequest(
                idempotency_key=uuid4().hex,
                expected_revision=current.revision,
                issue_id=current.issues[0].id,
            ),
        )
        self.run()
        return self.view(order)

    def approve_execute(self, order, action):
        current = self.command(order, "controller", "approve_action", action_id=action.id)
        return self.command(
            order,
            "executor",
            "execute_action",
            action_id=action.id,
            approval_id=current.approvals[-1].id,
        )


def test_actual_investigator_requests_the_missing_accepted_amendment(tmp_path):
    flow = Flow(tmp_path / "connected.sqlite3")
    order = flow.investigate(flow.create())
    assert order.investigations[-1].status == "COMPLETE", order.investigations[-1].error
    assert order.issues[0].state == "WAITING_CUSTOMER"
    question = next(q for q in order.issues[0].questions if q.status == "OPEN")
    flow.command(
        order,
        "customer",
        "answer",
        issue_id=order.issues[0].id,
        question_id=question.id,
        text="Due date is additional scope.",
    )
    flow.run()
    current = flow.view(order)
    assert current.investigations[-1].status == "COMPLETE"
    assert not any(q.status == "OPEN" for q in current.issues[0].questions)
    assert any(a.kind == "QUOTE" and a.issue_id == current.issues[0].id for a in current.actions)


def test_independent_correction_does_not_invalidate_an_executed_new_scope_quote(tmp_path):
    flow = Flow(tmp_path / "independent.sqlite3")
    order = flow.create(disputed_field=None)
    quote = next(a for a in order.actions if a.kind == "QUOTE")
    order = flow.approve_execute(order, quote)
    change_id = order.change_orders[-1].id
    failed_ids = [j.id for j in order.jobs if j.processing == "FAILED"]
    flow.command(order, "provider", "correct", job_ids=failed_ids)
    flow.run()
    flow.command(order, "customer", "accept_delivery", job_ids=failed_ids)
    order = flow.command(order, "customer", "accept_change", change_order_id=change_id)
    assert order.change_orders[-1].status == "ACCEPTED"


def test_already_correct_disputed_field_closes_without_cost_or_extra_artifact(tmp_path):
    flow = Flow(tmp_path / "no-remedy.sqlite3")
    order = flow.create(
        failed_count=0,
        requested_fields=[],
        agreement_fields=[
            "invoice_number",
            "vendor",
            "amount",
            "currency",
            "due_date",
        ],
    )
    order = flow.investigate(order)
    action = next(a for a in reversed(order.actions) if a.issue_id == order.issues[0].id)
    assert action.kind == "NO_REMEDY"
    before = (len(order.evidence), len(order.finance.postings), order.finance.correction_cost_minor)
    order = flow.approve_execute(order, action)
    assert order.issues[0].state == "RESOLVED"
    assert before == (
        len(order.evidence),
        len(order.finance.postings),
        order.finance.correction_cost_minor,
    )


def test_accepted_evidence_clears_obsolete_questions(tmp_path):
    flow = Flow(tmp_path / "amendment.sqlite3")
    order = flow.investigate(flow.create())
    assert any(q.status == "OPEN" for q in order.issues[0].questions)
    effective = flow.now - timedelta(seconds=1)
    order = flow.command(
        order, "customer", "amend_agreement", fields=["due_date"], effective_at=effective
    )
    amendment = order.agreement.amendments[-1]
    order = flow.command(
        order,
        "provider",
        "amend_agreement",
        amendment_id=amendment.id,
        fields=amendment.fields,
        effective_at=amendment.effective_at,
    )
    order = flow.investigate(order)
    assert order.investigations[-1].status == "COMPLETE", order.investigations[-1].error
    assert not any(q.status == "OPEN" for q in order.issues[0].questions)
    assert any(a.kind == "INCLUDED_FIELD" and a.status == "PROPOSED" for a in order.actions)
