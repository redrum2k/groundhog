import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.contracts.models import SettlementIntent
from app.payments import get_payment_adapter
from app.payments.interfaces import AuthorizationRequest, PaymentReceipt


def test_default_is_durable_explicit_mock(tmp_path, monkeypatch, capture_intent):
    monkeypatch.delenv("PAYMENT_ADAPTER", raising=False)
    path = tmp_path / "payments.sqlite3"
    adapter = get_payment_adapter(path)
    try:
        receipt = asyncio.run(adapter.execute(capture_intent))
        assert receipt.mode == "mock"
        assert receipt.status == "mock"
        assert receipt.transaction_id is None
        assert asyncio.run(adapter.execute(capture_intent)) == receipt
    finally:
        adapter.close()

    restarted = get_payment_adapter(path)
    try:
        assert asyncio.run(restarted.reconcile(capture_intent.idempotency_key)) == receipt
        assert asyncio.run(restarted.execute(capture_intent)) == receipt
        assert asyncio.run(restarted.reconcile("unknown-key")) is None
        changed = capture_intent.model_dump()
        changed["proposal"]["evidence_version"] = 2
        with pytest.raises(ValueError, match="different operation or payload"):
            asyncio.run(restarted.execute(SettlementIntent.model_validate(changed)))
    finally:
        restarted.close()


def test_mock_supports_authorization_and_release(tmp_path, investigation_input, capture_intent):
    adapter = get_payment_adapter(tmp_path / "payments.sqlite3")
    try:
        authorization = AuthorizationRequest(
            order_id=investigation_input.snapshot.order_id,
            snapshot_id=investigation_input.snapshot.snapshot_id,
            amount=investigation_input.snapshot.price,
            expires_at=investigation_input.delivery.delivered_at + timedelta(minutes=5),
            idempotency_key="authorize-order-1",
        )
        receipt = asyncio.run(adapter.authorize(authorization))
        assert receipt.operation == "authorize"
        assert receipt.status == "mock"
        release = SettlementIntent.model_validate(
            {
                **capture_intent.model_dump(),
                "action": "release",
                "idempotency_key": "release-order-1",
            }
        )
        assert asyncio.run(adapter.execute(release)).operation == "release"
        reused = SettlementIntent.model_validate(
            {**release.model_dump(), "idempotency_key": authorization.idempotency_key}
        )
        with pytest.raises(ValueError, match="different operation or payload"):
            asyncio.run(adapter.execute(reused))
    finally:
        adapter.close()


@pytest.mark.parametrize("mode", ["live", "base_sepolia"])
def test_legacy_adapter_cannot_be_enabled(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("PAYMENT_ADAPTER", mode)
    with pytest.raises(ValueError, match="PAYMENT_ADAPTER|legacy payment adapter"):
        get_payment_adapter(tmp_path / "payments.sqlite3")


@pytest.mark.parametrize("status", ["submitted", "uncertain", "confirmed"])
def test_mock_cannot_claim_live_outcome(status):
    with pytest.raises(ValidationError, match="mock receipts"):
        PaymentReceipt(
            idempotency_key="key",
            operation_id="mock_1",
            operation="capture",
            mode="mock",
            status=status,
        )
