from datetime import timedelta

import pytest

from app.contracts.models import SettlementIntent
from app.runtime.policy import CaptureContext, decide_remedy, validate_capture


def check(request, intent, context, seconds=60):
    validate_capture(
        request.snapshot,
        request.delivery,
        intent,
        context,
        now=request.delivery.delivered_at + timedelta(seconds=seconds),
    )


def context_with(context, **changes):
    return CaptureContext.model_validate({**context.model_dump(), **changes})


def test_capture_at_review_expiry(investigation_input, capture_intent, capture_context):
    check(investigation_input, capture_intent, capture_context, 60)


def test_capture_before_review_expiry_requires_acceptance(
    investigation_input, capture_intent, capture_context
):
    with pytest.raises(ValueError, match="acceptance or review expiry"):
        check(investigation_input, capture_intent, capture_context, 59)
    accepted = context_with(capture_context, customer_acceptance=investigation_input.proposal)
    check(investigation_input, capture_intent, accepted, 1)


@pytest.mark.parametrize(
    "changes",
    [
        {"case_state": "open"},
        {"case_state": "human_review"},
        {"order_state": "human_review"},
        {"delivery_state": "failed"},
        {"delivery_state": "pending_verification"},
        {"verification_binding": None},
        {"payment_state": "submitted"},
        {"payment_state": "uncertain"},
        {"payment_state": "mock"},
        {"payment_state": "captured"},
    ],
)
def test_capture_fails_closed_even_with_acceptance(
    investigation_input, capture_intent, capture_context, changes
):
    context = context_with(
        capture_context, customer_acceptance=investigation_input.proposal, **changes
    )
    with pytest.raises(ValueError):
        check(investigation_input, capture_intent, context)


def test_authorization_expiry_is_independent(investigation_input, capture_intent, capture_context):
    context = context_with(
        capture_context,
        customer_acceptance=investigation_input.proposal,
        authorization_expires_at=investigation_input.delivery.delivered_at + timedelta(seconds=30),
    )
    with pytest.raises(ValueError, match="authorization has expired"):
        check(investigation_input, capture_intent, context, 30)


@pytest.mark.parametrize("field", ["delivery_version", "evidence_version", "proposal_version"])
def test_stale_intent_cannot_capture(investigation_input, capture_intent, capture_context, field):
    data = capture_intent.model_dump()
    data["proposal"][field] = 2
    intent = SettlementIntent.model_validate(data)
    with pytest.raises(ValueError, match="stale"):
        check(investigation_input, intent, capture_context)


@pytest.mark.parametrize("approval", ["customer_acceptance", "verification_binding"])
@pytest.mark.parametrize("field", ["delivery_version", "evidence_version", "proposal_version"])
def test_stale_approvals_cannot_capture(
    investigation_input, capture_intent, capture_context, approval, field
):
    stale = investigation_input.proposal.model_dump()
    stale[field] = 2
    context = context_with(capture_context, **{approval: stale})
    with pytest.raises(ValueError):
        check(investigation_input, capture_intent, context)


def test_capture_cannot_add_a_complaint_charge(
    investigation_input, capture_intent, capture_context
):
    data = capture_intent.model_dump()
    data["amount"]["amount_minor"] += 1
    intent = SettlementIntent.model_validate(data)
    with pytest.raises(ValueError, match="accepted price"):
        check(investigation_input, intent, capture_context)


@pytest.mark.parametrize(
    "assessment,used,failed,expected",
    [
        ("provider_defect", 0, False, "free_regeneration"),
        ("provider_defect", 1, False, "human_review"),
        ("ambiguous", 0, False, "human_review"),
        ("unsupported", 0, False, "no_remedy"),
        ("unsupported", 1, True, "human_review"),
        ("provider_defect", 1, True, "human_review"),
    ],
)
def test_one_regeneration_then_escalation(assessment, used, failed, expected):
    assert decide_remedy(assessment, used, regeneration_failed=failed) == expected
