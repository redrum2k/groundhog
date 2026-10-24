import hashlib
import json
from pathlib import Path

from app.contracts.models import SettlementIntent
from app.payments.interfaces import AuthorizationRequest, PaymentReceipt
from app.storage.mock_journal import MockPaymentJournal


def mock_receipt(key: str, operation: str) -> PaymentReceipt:
    return PaymentReceipt(
        idempotency_key=key,
        operation_id="mock_" + hashlib.sha256(key.encode()).hexdigest(),
        operation=operation,
        mode="mock",
        status="mock",
    )


class MockPaymentAdapter:
    """Local simulation only: no money moves and no receipt confirms settlement."""

    def __init__(self, journal_path: Path):
        self._journal = MockPaymentJournal(journal_path)

    def _record(
        self, operation: str, request: AuthorizationRequest | SettlementIntent
    ) -> PaymentReceipt:
        payload = json.dumps(
            {"operation": operation, "request": request.model_dump(mode="json")}, sort_keys=True
        )
        receipt = mock_receipt(request.idempotency_key, operation)
        stored = self._journal.record(request.idempotency_key, payload, receipt.model_dump_json())
        return PaymentReceipt.model_validate_json(stored)

    async def authorize(self, request: AuthorizationRequest) -> PaymentReceipt:
        return self._record("authorize", request)

    async def execute(self, intent: SettlementIntent) -> PaymentReceipt:
        return self._record(intent.action, intent)

    async def reconcile(self, idempotency_key: str) -> PaymentReceipt | None:
        stored = self._journal.lookup(idempotency_key)
        return PaymentReceipt.model_validate_json(stored) if stored else None

    def close(self) -> None:
        self._journal.close()
