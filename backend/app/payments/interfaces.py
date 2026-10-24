from typing import Literal, Protocol

from pydantic import AwareDatetime, model_validator

from app.contracts.models import Contract, Money, SettlementIntent, Text


class AuthorizationRequest(Contract):
    order_id: Text
    snapshot_id: Text
    amount: Money
    expires_at: AwareDatetime
    idempotency_key: Text


class PaymentReceipt(Contract):
    idempotency_key: Text
    operation_id: Text
    operation: Literal["authorize", "capture", "release"]
    mode: Literal["mock", "live"]
    status: Literal["mock", "submitted", "uncertain", "confirmed", "failed"]
    transaction_id: Text | None = None

    @model_validator(mode="after")
    def prevent_false_confirmation(self) -> "PaymentReceipt":
        if self.mode == "mock" and (self.status != "mock" or self.transaction_id is not None):
            raise ValueError(
                "mock receipts cannot claim a live transaction or confirmed settlement"
            )
        if self.mode == "live" and self.status == "mock":
            raise ValueError("live receipts cannot use mock status")
        return self


class PaymentAdapter(Protocol):
    async def authorize(self, request: AuthorizationRequest) -> PaymentReceipt:
        """Persist the key/request before any external effect; submission is not confirmation."""
        ...

    async def execute(self, intent: SettlementIntent) -> PaymentReceipt:
        """Runtime supplies an authorized intent after deterministic checks and reservation.

        Release also requires application authority; it is not a customer cancellation API.
        A live adapter must reconcile an uncertain/submitted operation before any retry.
        """
        ...

    async def reconcile(self, idempotency_key: str) -> PaymentReceipt | None:
        """Read authoritative outcome; absence alone is not permission to resubmit live work."""
        ...
