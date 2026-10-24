"""Stable public errors and startup capabilities; never echo sensitive request inputs."""

from typing import Literal

from app.contracts.models import Contract
from app.contracts.payments import PaymentMode


class ValidationIssue(Contract):
    loc: tuple[str | int, ...]
    msg: str
    type: str


class ErrorResponse(Contract):
    detail: str
    issues: tuple[ValidationIssue, ...] = ()


class Capabilities(Contract):
    status: Literal["ok"] = "ok"
    primary_product: Literal["aggregate_dataset"] = "aggregate_dataset"
    brokerage_policy: Literal["aggregate-brokerage-v1"] = "aggregate-brokerage-v1"
    contract_version: Literal["catalog-api-v1"] = "catalog-api-v1"
    payment_policy: Literal["catalog-payments-v1"] = "catalog-payments-v1"
    payment_mode: PaymentMode = "mock"
    live_settlement_enabled: bool = False
    buyer_signature_validation: bool = True
    mock_funding_requires_authorization: bool = True
    live_adapter: Literal["planned", "disabled", "ready", "unavailable"] = "disabled"
    customer_authentication: bool = False
