from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.models import (
    AcceptedPolicy,
    CaseState,
    DeliveryState,
    DeliveryVersion,
    EvidencePointer,
    EvidenceReference,
    InvestigationInput,
    Money,
    OrderSnapshot,
    OrderState,
    PaymentState,
    ProposalBinding,
    SettlementIntent,
)
from app.runtime.policy import CaptureContext


@pytest.fixture
def investigation_input():
    source = EvidenceReference(
        evidence_id="input-1",
        version=1,
        sha256="a" * 64,
        storage_key="orders/order-1/inputs/input-1/v1",
        media_type="application/pdf",
        kind="accepted_input",
    )
    artifact = EvidenceReference(
        evidence_id="output-1",
        version=1,
        sha256="b" * 64,
        storage_key="orders/order-1/deliveries/v1/output-1",
        media_type="application/pdf",
        kind="delivery_artifact",
    )
    structured = tuple(
        EvidenceReference(
            evidence_id=f"{reference.evidence_id}-records",
            version=1,
            sha256=digest * 64,
            storage_key=f"{reference.storage_key}/structured",
            media_type="application/json",
            kind="structured_data",
            derived_from=(
                EvidencePointer(
                    evidence_id=reference.evidence_id,
                    version=reference.version,
                    sha256=reference.sha256,
                ),
            ),
        )
        for reference, digest in ((source, "c"), (artifact, "d"))
    )
    accepted_at = datetime(2026, 10, 23, 12, tzinfo=UTC)
    snapshot = OrderSnapshot(
        order_id="order-1",
        snapshot_id="snapshot-1",
        accepted_at=accepted_at,
        accepted_brief="Preserve every input record in the output.",
        input_versions=(source,),
        structured_data=(structured[0],),
        price=Money(amount_minor=1000, currency="USD", decimals=2),
        policy=AcceptedPolicy(policy_version="demo-v1"),
    )
    delivery = DeliveryVersion(
        order_id=snapshot.order_id,
        snapshot_id=snapshot.snapshot_id,
        version=1,
        delivered_at=accepted_at + timedelta(seconds=10),
        artifacts=(artifact,),
        structured_data=(structured[1],),
    )
    return InvestigationInput(
        case_id="case-1",
        snapshot=snapshot,
        delivery=delivery,
        proposal=ProposalBinding(
            order_id=snapshot.order_id,
            snapshot_id=snapshot.snapshot_id,
            delivery_version=1,
            evidence_version=1,
            proposal_version=1,
        ),
        complaint="An input record appears to be missing.",
        evidence=(source, artifact, *structured),
    )


@pytest.fixture
def capture_intent(investigation_input):
    return SettlementIntent(
        proposal=investigation_input.proposal,
        action="capture",
        amount=investigation_input.snapshot.price,
        authorization_id="authorization-1",
        idempotency_key="order-1-capture-v1",
    )


@pytest.fixture
def capture_context(investigation_input):
    return CaptureContext(
        current_proposal=investigation_input.proposal,
        order_state=OrderState.DELIVERED,
        delivery_state=DeliveryState.PASSED,
        case_state=CaseState.NONE,
        payment_state=PaymentState.AUTHORIZED,
        verification_binding=investigation_input.proposal,
        customer_acceptance=None,
        authorization_id="authorization-1",
        authorized_amount=investigation_input.snapshot.price,
        authorization_expires_at=investigation_input.delivery.delivered_at + timedelta(minutes=5),
    )
