"""Catalog-native accepted payment terms and public state; never expose signing capabilities."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    AwareDatetime,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
    model_validator,
)

from app.contracts.models import Contract, Money, Text


def unsigned(value):
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and (value == "0" or not value.startswith("0"))
    ):
        value = int(value)
    if type(value) is not int or not 0 <= value < 2**256:
        raise ValueError(
            "blockchain quantities require an unsigned integer or canonical decimal string"
        )
    return value


UInt = Annotated[
    int,
    BeforeValidator(unsigned),
    PlainSerializer(str, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": "^(0|[1-9][0-9]*)$"}),
]
Address = Annotated[str, StringConstraints(pattern=r"^0x[a-fA-F0-9]{40}$")]
Hash32 = Annotated[str, StringConstraints(pattern=r"^0x[a-fA-F0-9]{64}$")]
PaymentMode = Literal["mock", "base_sepolia"]
PaymentAction = Literal["fund", "capture", "void", "reclaim"]
PaymentAccountState = Literal[
    "blocked_parent",
    "awaiting_signature",
    "funding_pending",
    "funded",
    "capture_pending",
    "captured",
    "void_pending",
    "voided",
    "uncertain",
    "failed",
    "expired_not_returned",
    "reorg_hold",
]
OperationState = Literal[
    "reserved", "signed", "submitted", "uncertain", "confirmed", "failed", "invalidated", "orphaned"
]


class PaymentInfo(Contract):
    operator: Address
    payer: Address
    receiver: Address
    token: Address
    max_amount: Annotated[
        UInt, Field(gt=0, lt=2**120, validation_alias=AliasChoices("max_amount", "maxAmount"))
    ]
    pre_approval_expiry: Annotated[
        UInt,
        Field(lt=2**48, validation_alias=AliasChoices("pre_approval_expiry", "preApprovalExpiry")),
    ]
    authorization_expiry: Annotated[
        UInt,
        Field(
            lt=2**48, validation_alias=AliasChoices("authorization_expiry", "authorizationExpiry")
        ),
    ]
    refund_expiry: Annotated[
        UInt, Field(lt=2**48, validation_alias=AliasChoices("refund_expiry", "refundExpiry"))
    ]
    min_fee_bps: Literal[0] = 0
    max_fee_bps: Literal[0] = 0
    fee_receiver: Address
    salt: UInt

    @model_validator(mode="after")
    def supported_terms(self):
        if not self.pre_approval_expiry <= self.authorization_expiry <= self.refund_expiry:
            raise ValueError(
                "payment deadlines must be ordered preApproval <= authorization <= refund"
            )
        zero = "0x" + "0" * 40
        if any(
            address.lower() == zero
            for address in (self.operator, self.payer, self.receiver, self.token)
        ):
            raise ValueError("payer, receiver, operator and token must be nonzero")
        if self.operator.lower() in (self.receiver.lower(), self.payer.lower()):
            raise ValueError("dedicated operator must differ from payer and provider")
        return self

    def to_contract_tuple(self):
        return (
            self.operator,
            self.payer,
            self.receiver,
            self.token,
            self.max_amount,
            self.pre_approval_expiry,
            self.authorization_expiry,
            self.refund_expiry,
            self.min_fee_bps,
            self.max_fee_bps,
            self.fee_receiver,
            self.salt,
        )


class PaymentTerms(Contract):
    policy_version: Literal["catalog-payments-v1"] = "catalog-payments-v1"
    payment_id: Text
    mode: PaymentMode
    chain_id: Literal[84532] = 84532
    asset_address: Address
    symbol: Literal["USDC"] = "USDC"
    decimals: Literal[6] = 6
    amount_atomic: Annotated[UInt, Field(gt=0, lt=2**120)]
    payment_info: PaymentInfo
    escrow_address: Address
    collector_address: Address
    deployment_version: Literal["v1.1.0"] = "v1.1.0"
    source_commit: Literal["b748fdd7a830a655a19a530edcf2a94b9dc7d25f"] = (
        "b748fdd7a830a655a19a530edcf2a94b9dc7d25f"
    )
    payment_hash: Hash32
    authorization_nonce: Hash32
    pricing_rule: Literal["catalog-usd-usdc-1to1-v1", "isolated-test-usdc-0.10-v1"]
    display_amount: Money
    settlement_terms: Text
    confirmations: Annotated[int, Field(strict=True, ge=2, le=100)] = 2

    @model_validator(mode="after")
    def exact_asset_amount(self):
        if self.asset_address.lower() != self.payment_info.token.lower():
            raise ValueError("payment token differs from accepted asset")
        if self.amount_atomic != self.payment_info.max_amount:
            raise ValueError("full accepted amount must equal PaymentInfo.maxAmount")
        if self.display_amount.currency != "USD" or self.display_amount.decimals != 2:
            raise ValueError("this demo requires USD cents for display pricing")
        if self.amount_atomic != self.display_amount.amount_minor * 10000:
            raise ValueError("accepted 1 USD : 1 USDC conversion must be exact")
        if self.pricing_rule == "isolated-test-usdc-0.10-v1" and self.amount_atomic != 100000:
            raise ValueError("isolated spike is exactly 0.10 test USDC")
        if (
            self.mode == "base_sepolia"
            and self.asset_address.lower() != "0x036cbd53842c5426634e7929541ec2318f3dcf7e"
        ):
            raise ValueError("only Base Sepolia test USDC is supported")
        return self


class PaymentBinding(Contract):
    snapshot_id: Text
    evidence_revision: Annotated[int, Field(strict=True, ge=1)]
    delivery_version: Annotated[int, Field(strict=True, ge=0)]


class CatalogPaymentIntent(Contract):
    operation_id: Text
    payment_id: Text
    order_id: Text
    snapshot_id: Text
    binding: PaymentBinding
    action: PaymentAction
    amount_atomic: Annotated[UInt, Field(gt=0)]
    chain_id: Literal[84532] = 84532
    payment_hash: Hash32
    idempotency_key: Text
    reason: Text
    mode: PaymentMode


class BlockEvidence(Contract):
    transaction_hash: Hash32
    block_number: UInt
    block_hash: Hash32
    observed_head: UInt
    confirmations: Annotated[int, Field(strict=True, ge=0)]
    canonical: bool
    event: Literal["PaymentAuthorized", "PaymentCaptured", "PaymentVoided", "PaymentReclaimed"]
    payment_hash: Hash32
    amount_atomic: UInt


class EscrowObservation(Contract):
    payment_hash: Hash32
    has_collected_payment: bool
    capturable_amount: UInt
    refundable_amount: UInt
    block_number: UInt
    block_hash: Hash32
    token_store: Address | None = None
    buyer_balance: UInt | None = None
    provider_balance: UInt | None = None
    token_store_balance: UInt | None = None


class PaymentOperation(Contract):
    operation_id: Text
    intent: CatalogPaymentIntent
    fingerprint: Text
    state: OperationState = "reserved"
    created_at: AwareDatetime
    updated_at: AwareDatetime
    nonce: UInt | None = None
    transaction_hash: Hash32 | None = None
    block_evidence: BlockEvidence | None = None
    observation: EscrowObservation | None = None
    error: Text | None = None
    reconciliation_status: Literal[
        "not_submitted", "pending", "confirmed", "failed", "uncertain", "orphaned"
    ] = "not_submitted"
    attempts: Annotated[int, Field(strict=True, ge=0)] = 0

    @model_validator(mode="after")
    def simulated_is_not_chain(self):
        if self.intent.mode == "mock" and (self.transaction_hash or self.block_evidence):
            raise ValueError("mock operations cannot have live transaction evidence")
        return self


class PaymentAccount(Contract):
    payment_id: Text
    order_id: Text
    snapshot_id: Text
    terms: PaymentTerms
    state: PaymentAccountState
    blocked_by_payment_id: Text | None = None
    latest_observation: EscrowObservation | None = None
    last_error: Text | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class TypedDataField(Contract):
    name: Text
    type: Text


class AuthorizationTypes(Contract):
    EIP712Domain: tuple[TypedDataField, ...]
    ReceiveWithAuthorization: tuple[TypedDataField, ...]


class AuthorizationDomain(Contract):
    name: Text
    version: Literal["2"] = "2"
    chainId: Literal[84532] = 84532
    verifyingContract: Address


class AuthorizationMessage(Contract):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    from_: Annotated[Address, Field(alias="from")]
    to: Address
    value: UInt
    validAfter: UInt
    validBefore: UInt
    nonce: Hash32


class AuthorizationTypedData(Contract):
    types: AuthorizationTypes
    primaryType: Literal["ReceiveWithAuthorization"]
    domain: AuthorizationDomain
    message: AuthorizationMessage


class FundingPreparation(Contract):
    funding_attempt_id: Text
    payment_id: Text
    order_id: Text
    binding: PaymentBinding
    terms: PaymentTerms
    typed_data: AuthorizationTypedData
    prepared_at: AwareDatetime
    expires_at: AwareDatetime


class FundingAuthorization(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    expected_binding: PaymentBinding
    idempotency_key: Text
    funding_attempt_id: Text
    payment_hash: Hash32
    signature: Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{130}$")] | None = Field(
        default=None, repr=False
    )
    simulate: bool = False

    @model_validator(mode="after")
    def one_authorization(self):
        if bool(self.signature) == self.simulate:
            raise ValueError("provide a buyer signature or explicit mock simulation")
        return self


class PaymentWorkResult(Contract):
    processed: Annotated[int, Field(strict=True, ge=0)]
    simulated: bool = True


class PaymentView(Contract):
    payment: PaymentAccount
    operations: tuple[PaymentOperation, ...]
    explorer_links: tuple[Text, ...] = ()
    simulated: bool
    finality_note: Literal["Receipt confirmation threshold is not Ethereum/L1 finality."] = (
        "Receipt confirmation threshold is not Ethereum/L1 finality."
    )
