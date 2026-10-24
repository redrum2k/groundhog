import pytest

from app.contracts.catalog import ApprovalCommand, SourcePolicy
from app.orders.service import DomainError

from .fixtures import accepted, cmd, upload


def require_approval(service, order):
    # Test setup: represent an accepted provider policy requiring both actors.
    quote = order.snapshot.quote
    terms = quote.specification.terms.model_copy(
        update={"source_policy": SourcePolicy(evidence_repair="customer_and_provider")}
    )
    quote = quote.model_copy(
        update={"specification": quote.specification.model_copy(update={"terms": terms})}
    )
    order.snapshot = order.snapshot.model_copy(update={"quote": quote})
    with service.repository.transaction() as db:
        service._save(db, order)
    return order


def test_evidence_repair_requires_both_roles_when_policy_requires_consent(setup):
    service, _, fixtures = setup
    order = require_approval(service, accepted(service))
    order = service.run_one(order.snapshot.order_id)
    order = upload(service, order, fixtures["repair"].artifact)
    order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "pending_approval"
    approval = order.approvals[-1]
    before = order.binding
    order = service.mutate(
        order.snapshot.order_id,
        "approval_customer",
        cmd(
            order,
            "customer",
            ApprovalCommand,
            approval_id=approval.approval_id,
            actor="customer:test",
            accept=True,
        ),
    )
    assert order.authority_state == "pending_consent" and order.binding == before
    order = service.mutate(
        order.snapshot.order_id,
        "approval_provider",
        cmd(
            order,
            "provider",
            ApprovalCommand,
            approval_id=approval.approval_id,
            actor="ignored-client-name",
            accept=True,
        ),
        actor="provider:trusted",
    )
    assert order.binding.evidence_revision == before.evidence_revision + 1
    assert order.authority_state == "clear" and order.sources[1].version == 2
    assert order.approvals[-1].provider_actor == "provider:trusted"
    assert service.run_one(order.snapshot.order_id).order_state == "delivered"


def test_rejected_approval_preserves_original_contract_and_holds_payment(setup):
    service, _, fixtures = setup
    order = require_approval(service, accepted(service))
    snapshot = order.snapshot
    order = service.run_one(order.snapshot.order_id)
    order = upload(service, order, fixtures["repair"].artifact)
    order = service.run_one(order.snapshot.order_id)
    approval = order.approvals[-1]
    order = service.mutate(
        order.snapshot.order_id,
        "approval_customer",
        cmd(
            order,
            "reject",
            ApprovalCommand,
            approval_id=approval.approval_id,
            actor="customer:test",
            accept=False,
        ),
    )
    assert order.authority_state == "rejected" and order.order_state == "human_review"
    assert (
        order.snapshot == snapshot and order.sources == snapshot.quote.sources and not order.ledger
    )


def test_approval_expiry_does_not_reset_original_deadlines(setup):
    service, clock, fixtures = setup
    order = require_approval(service, accepted(service))
    order = service.run_one(order.snapshot.order_id)
    deadline = order.repair_deadline
    order = upload(service, order, fixtures["repair"].artifact)
    order = service.run_one(order.snapshot.order_id)
    assert order.repair_deadline == deadline
    clock.advance(120)
    with pytest.raises(DomainError):
        service.mutate(
            order.snapshot.order_id,
            "approval_customer",
            cmd(
                order,
                "late",
                ApprovalCommand,
                approval_id=order.approvals[-1].approval_id,
                actor="customer:test",
                accept=True,
            ),
        )
    assert service.get(order.snapshot.order_id).order_state == "human_review"
