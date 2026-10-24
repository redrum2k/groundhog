from datetime import timedelta

import pytest

from app.contracts.jobflow import InvestigationRequest, OrderCreate
from app.contracts.models import OrderState
from app.runtime.jobflow import Jobflow
from app.storage.jobflow import DomainError


def clean(h, **kwargs):
    return h.service.create(
        h.actors["customer"],
        OrderCreate(
            idempotency_key="clean",
            document_count=3,
            failed_count=0,
            disputed_field=None,
            requested_fields=[],
            **kwargs,
        ),
    )


def test_same_authority_real_pdf_early_evidence_capture_and_restart(h):
    order = clean(h)
    base = order.base_order.order
    assert base.authorization_receipt.operation == "authorize"
    assert base.review_deadline == h.now + timedelta(seconds=600)
    assert not base.ledger
    assert order.finance.received_minor == 0
    document = base.deliveries[0].artifacts[0]
    raw, _, _ = h.service.artifact(h.actors["customer"], order.id, document.evidence_id)
    assert raw.startswith(b"%PDF")
    result = h.cmd(order, "investigator", "verify_base")
    assert result.base_order.order.payment_phase == "booked"
    assert len(result.base_order.order.result.checks) == 8
    assert result.finance.received_minor == 300
    with h.service.store.connect() as db:
        shared = h.service.base.repository.get(db, order.id)
        assert shared == result.base_order.order
        assert db.execute("SELECT count(*) FROM jf_postings").fetchone()[0] == 0
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now)
    assert h.get(order).base_order.order.ledger == result.base_order.order.ledger


def test_cutoff_books_unreviewed_delivery_without_marking_verified(h):
    order = clean(h)
    h.now += timedelta(seconds=600)
    closed = h.get(order)
    assert closed.base_order.order.payment_phase == "booked"
    assert closed.base_order.display_status == "needs_review"
    assert closed.base_order.order.result is None


def test_dispute_cutoff_holds_and_authorization_expiry_is_independent(h):
    order = clean(h, authorization_seconds=1200)
    h.now += timedelta(seconds=100)
    disputed = h.cmd(
        order,
        "customer",
        "open_dispute",
        job_ids=[order.jobs[0].id],
        fields=["due_date"],
        text="Was due date included?",
    )
    assert disputed.base_order.order.review_deadline == h.now + timedelta(seconds=600)
    h.now += timedelta(seconds=600)
    held = h.get(order)
    assert held.base_order.order.payment_phase == "held"
    assert held.base_order.order.order_state == OrderState.HUMAN_REVIEW
    assert not held.base_order.order.ledger


def test_authorization_expires_before_review_no_capture(h):
    order = clean(h, authorization_seconds=100)
    h.now += timedelta(seconds=100)
    expired = h.get(order)
    assert expired.base_order.order.payment_phase == "expired"
    with pytest.raises(DomainError):
        h.cmd(order, "investigator", "verify_base")
    assert expired.finance.received_minor == 0


def test_processing_failure_holds_until_actual_register_exists(h):
    order = h.create(disputed_field=None, requested_fields=[])
    assert order.base_order.display_status == "operational_failure"
    assert not order.base_order.order.deliveries
    with pytest.raises(DomainError):
        h.cmd(order, "executor", "receive_payment")
    h.cmd(order, "provider", "correct")
    h.drain()
    corrected = h.get(order)
    assert len(corrected.base_order.order.deliveries) == 1
    assert corrected.base_order.order.payment_phase == "open"
    assert corrected.finance.received_minor == 0
    captured = h.cmd(corrected, "investigator", "verify_base")
    assert captured.finance.received_minor == 300
    assert captured.finance.correction_cost_minor == 1


def test_pending_job_dispute_cannot_be_bypassed_with_pdf_only_verdict(h):
    order = h.create()
    h.cmd(order, "provider", "correct")
    h.drain()
    assert h.get(order).base_order.order.payment_phase == "held"
    with pytest.raises(DomainError, match="Unresolved"):
        h.cmd(order, "investigator", "verify_base")


def test_change_quote_acceptance_is_not_payment_authority(h):
    order, change = h.quote(h.create())
    h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    with pytest.raises(DomainError, match="payment authorization"):
        h.cmd(order, "executor", "receive_payment", change_order_id=change.id)
    authorized = h.cmd(order, "customer", "authorize_change", change_order_id=change.id)
    assert authorized.change_orders[0].payment_authorization.receipt.operation == "authorize"
    assert authorized.finance.received_minor == 0
    h.cmd(order, "executor", "receive_payment", change_order_id=change.id)
    h.drain()
    assert h.get(order).finance.received_minor == 24
    assert not h.get(order).base_order.order.ledger


def test_payment_authority_rechecked_when_queued_work_executes(h):
    order, change = h.quote(h.create())
    h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    h.cmd(order, "customer", "authorize_change", change_order_id=change.id)
    h.cmd(order, "executor", "receive_payment", change_order_id=change.id)
    h.now += timedelta(hours=1)
    h.drain()
    result = h.get(order)
    assert result.finance.operations[-1].status == "FAILED"
    assert result.finance.received_minor == 0


def test_native_deadline_sweep_respects_signed_future_scope(h):
    order = clean(h)
    effective = h.now + timedelta(seconds=100)
    proposed = h.cmd(
        order, "customer", "amend_agreement", fields=["due_date"], effective_at=effective
    )
    h.cmd(
        order,
        "provider",
        "amend_agreement",
        fields=["due_date"],
        effective_at=effective,
        amendment_id=proposed.agreement.amendments[-1].id,
    )
    h.now += timedelta(seconds=600)
    h.service.base.expire_due()
    held = h.get(order)
    assert held.base_order.order.payment_phase == "held"
    assert not held.base_order.order.ledger


@pytest.mark.parametrize("fee", [0, 250])
def test_refuted_claim_uses_agreed_fee_or_separate_accepted_authorized_quote(h, fee):
    order = clean(h, additional_processing_fee_minor=fee)
    h.service.investigator = None
    disputed = h.cmd(
        order,
        "customer",
        "open_dispute",
        job_ids=[order.jobs[0].id],
        fields=["invoice_number"],
        text="Invoice number is missing",
    )
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key="dispute-evidence",
            expected_revision=disputed.revision,
            issue_id=disputed.issues[-1].id,
        ),
    )
    h.drain()
    action = next(a for a in h.get(order).actions if a.kind == "NO_REMEDY")
    approved = h.cmd(order, "controller", "approve_action", action_id=action.id)
    h.cmd(
        order,
        "executor",
        "execute_action",
        action_id=action.id,
        approval_id=approved.approvals[-1].id,
    )
    captured = h.cmd(order, "investigator", "verify_base")
    assert captured.finance.received_minor == 300 + fee
    if fee:
        assert [entry.kind for entry in captured.base_order.order.ledger] == [
            "base",
            "additional_processing",
        ]
    else:
        assert captured.base_order.order.requires_quote
        quoted = h.cmd(order, "controller", "quote_processing", amount_minor=75)
        assert quoted.finance.received_minor == 300
        accepted = h.cmd(
            order,
            "customer",
            "accept_processing_quote",
            processing_quote_id=quoted.base_order.order.quote.quote_id,
        )
        assert accepted.finance.received_minor == 375
        assert accepted.base_order.order.quote_authorization.amount.amount_minor == 75
        with pytest.raises(DomainError):
            h.cmd(
                order,
                "customer",
                "accept_processing_quote",
                processing_quote_id=quoted.base_order.order.quote.quote_id,
            )


def test_source_page_is_hash_bound_authorized_and_read_only(h):
    from fastapi.testclient import TestClient

    from app.main import create_app

    order = clean(h)
    source = order.jobs[0].source_id
    assert order.jobs[0].checks[0].citations[0].rectangle is not None
    with TestClient(create_app(h.service, worker=False)) as client:
        token = client.post("/api/jobflow/sessions", json={"actor_id": "customer"}).json()["token"]
        path = f"/api/jobflow/orders/{order.id}/artifacts/{source}/pages/1"
        assert client.get(path).status_code == 401
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.content.startswith(b"\x89PNG")
        assert response.headers["X-Source-SHA256"] == order.jobs[0].checks[0].citations[0].sha256
        assert h.get(order).revision == order.revision


def test_four_unique_invoices_in_six_pdfs_duplicate_and_conflicting_versions(h, monkeypatch):
    import json

    from app.provider.jobflow import invoice

    sequence = [(1, None), (2, None), (2, None), (3, None), (3, {"amount": "999.25"}), (4, None)]
    monkeypatch.setattr("app.orders.jobflow.invoice", lambda index: invoice(*sequence[index - 1]))
    order = h.service.create(
        h.actors["customer"],
        OrderCreate(
            idempotency_key="six-sources",
            document_count=6,
            failed_count=0,
            disputed_field=None,
            requested_fields=[],
        ),
    )
    reviewed = h.cmd(order, "investigator", "verify_base")
    sidecar = reviewed.base_order.order.deliveries[-1].structured_data[0]
    raw, _, _ = h.service.artifact(h.actors["customer"], order.id, sidecar.evidence_id)
    data = json.loads(raw)
    assert len(data["rows"]) == 3
    assert data["exceptions"][0]["invoice_number"] == "INV-0003"
    assert len(data["exceptions"][0]["sources"]) == 2
    assert data["totals"] == {"USD": "307.75"}
    assert (
        len(next(row for row in data["rows"] if row["invoice_number"] == "INV-0002")["sources"])
        == 2
    )
    assert reviewed.base_order.order.payment_phase == "booked"


def test_questions_are_bounded_across_job_issues(h):
    from app.contracts.jobflow import InvestigationOutcome, Question
    from app.runtime.jobflow_investigations import validate_outcome

    order = h.create()
    issue = order.issues[0]
    issue.questions = [
        Question(
            id=f"q-{index}",
            issue_id=issue.id,
            text="Evidence?",
            recipient="customer",
            status="ANSWERED",
        )
        for index in range(2)
    ]
    outcome = InvestigationOutcome(
        issue_id=issue.id,
        revision=order.revision,
        findings=[],
        questions=[Question(id="third", issue_id=issue.id, text="More?", recipient="customer")],
        recommendations=["HUMAN_REVIEW"],
        summary="Missing evidence",
        model_mode="DETERMINISTIC",
    )
    with pytest.raises(DomainError, match="two-question"):
        validate_outcome(order, outcome.model_dump(), {})
