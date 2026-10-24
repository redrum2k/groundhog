"""Offline encodings for the pinned Commerce Payments v1.1.0 EOA flow.

These helpers neither read an RPC nor sign or submit a transaction. A caller must
separately verify the token's onchain DOMAIN_SEPARATOR before requesting a live
buyer signature. Creating typed data is not funding or a deployment preflight.
"""

from collections.abc import Mapping
from typing import Any

from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data, hash_domain
from eth_utils import keccak, to_checksum_address

from app.contracts.payments import PaymentInfo, PaymentTerms
from app.payments.base_config import (
    BASE_CHAIN_ID,
    BASE_COLLECTOR_ADDRESS,
    BASE_ESCROW_ADDRESS,
    BASE_USDC_ADDRESS,
)

ZERO_ADDRESS = "0x" + "0" * 40
PAYMENT_INFO_TYPE = (
    "PaymentInfo(address operator,address payer,address receiver,address token,"
    "uint120 maxAmount,uint48 preApprovalExpiry,uint48 authorizationExpiry,"
    "uint48 refundExpiry,uint16 minFeeBps,uint16 maxFeeBps,address feeReceiver,uint256 salt)"
)
PAYMENT_INFO_TYPEHASH = keccak(text=PAYMENT_INFO_TYPE)
PAYMENT_INFO_ABI_TYPE = (
    "(address,address,address,address,uint120,uint48,uint48,uint48,uint16,uint16,address,uint256)"
)
SECP256K1_HALF_ORDER = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0


def payment_info_tuple(info: PaymentInfo) -> tuple:
    """Return exact Solidity field order, with checksummed ABI addresses."""
    values = list(info.to_contract_tuple())
    for index in (0, 1, 2, 3, 10):
        values[index] = to_checksum_address(values[index])
    return tuple(values)


def _payment_hash(values: tuple, chain_id: int, escrow_address: str) -> str:
    inner = keccak(encode(["bytes32", PAYMENT_INFO_ABI_TYPE], [PAYMENT_INFO_TYPEHASH, values]))
    return (
        "0x"
        + keccak(encode(["uint256", "address", "bytes32"], [chain_id, escrow_address, inner])).hex()
    )


def compute_payment_hash(
    info: PaymentInfo, chain_id: int = BASE_CHAIN_ID, escrow_address: str = BASE_ESCROW_ADDRESS
) -> str:
    """Match AuthCaptureEscrow.getHash, including chain and escrow binding."""
    return _payment_hash(payment_info_tuple(info), chain_id, escrow_address)


def compute_authorization_nonce(
    info: PaymentInfo, chain_id: int = BASE_CHAIN_ID, escrow_address: str = BASE_ESCROW_ADDRESS
) -> str:
    """Match TokenCollector._getHashPayerAgnostic without mutating accepted info."""
    values = list(payment_info_tuple(info))
    values[1] = ZERO_ADDRESS
    return _payment_hash(tuple(values), chain_id, escrow_address)


def validate_payment_terms(terms: PaymentTerms) -> None:
    """Reject stale hashes and unsupported chain, token or deployment substitutions."""
    if terms.chain_id != BASE_CHAIN_ID:
        raise ValueError("only Base Sepolia is supported")
    for actual, expected in (
        (terms.asset_address, BASE_USDC_ADDRESS),
        (terms.escrow_address, BASE_ESCROW_ADDRESS),
        (terms.collector_address, BASE_COLLECTOR_ADDRESS),
    ):
        if actual.lower() != expected.lower():
            raise ValueError("payment terms differ from the pinned Base Sepolia deployment")
    if terms.payment_hash.lower() != compute_payment_hash(
        terms.payment_info, terms.chain_id, terms.escrow_address
    ):
        raise ValueError("payment hash does not match immutable payment terms")
    if terms.authorization_nonce.lower() != compute_authorization_nonce(
        terms.payment_info, terms.chain_id, terms.escrow_address
    ):
        raise ValueError("authorization nonce does not match immutable payment terms")


def usdc_domain(name: str, *, chain_id: int = BASE_CHAIN_ID) -> dict[str, Any]:
    """Construct Circle v2 domain from a separately observed token name.

    Circle FiatTokenV2_2 fixes EIP-712 version to '2'; the returned value must
    still be compared to the actual DOMAIN_SEPARATOR before live use.
    """
    if not name or not name.strip() or chain_id != BASE_CHAIN_ID:
        raise ValueError("a token name and Base Sepolia chain are required")
    return {
        "name": name,
        "version": "2",
        "chainId": chain_id,
        "verifyingContract": BASE_USDC_ADDRESS,
    }


def verify_domain_separator(domain: Mapping[str, Any], observed_separator: str | bytes) -> None:
    """Check an externally supplied onchain observation; perform no network call."""
    try:
        observed = (
            bytes.fromhex(observed_separator.removeprefix("0x"))
            if isinstance(observed_separator, str)
            else bytes(observed_separator)
        )
    except (TypeError, ValueError):
        raise ValueError("invalid observed USDC domain separator") from None
    if len(observed) != 32 or hash_domain(dict(domain)) != observed:
        raise ValueError("USDC EIP-712 domain does not match observed DOMAIN_SEPARATOR")


def receive_authorization_typed_data(
    terms: PaymentTerms, domain: Mapping[str, Any]
) -> dict[str, Any]:
    """Exact ERC-3009 message; uint256 values use decimal strings for browser safety."""
    validate_payment_terms(terms)
    domain = dict(domain)
    if set(domain) != {"name", "version", "chainId", "verifyingContract"}:
        raise ValueError("USDC domain must have exactly name, version, chainId, verifyingContract")
    if (
        not isinstance(domain["name"], str)
        or not domain["name"].strip()
        or domain["version"] != "2"
        or domain["chainId"] != terms.chain_id
        or not isinstance(domain["verifyingContract"], str)
        or domain["verifyingContract"].lower() != terms.asset_address.lower()
    ):
        raise ValueError("USDC domain differs from accepted chain/token or Circle v2")
    domain["verifyingContract"] = to_checksum_address(domain["verifyingContract"])
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "ReceiveWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "ReceiveWithAuthorization",
        "domain": domain,
        "message": {
            "from": to_checksum_address(terms.payment_info.payer),
            "to": to_checksum_address(terms.collector_address),
            "value": str(terms.payment_info.max_amount),
            "validAfter": "0",
            "validBefore": str(terms.payment_info.pre_approval_expiry),
            "nonce": terms.authorization_nonce,
        },
    }


def verify_buyer_signature(
    terms: PaymentTerms,
    domain: Mapping[str, Any],
    signature: str | bytes,
    now_timestamp: int,
) -> bytes:
    """Recover the accepted payer and return raw collectorData r||s||v bytes.

    A successful recovery proves authorization of these exact terms only. It
    establishes neither funding nor unused authorization state on the chain.
    """
    if (
        type(now_timestamp) is not int
        or not 0 < now_timestamp < terms.payment_info.pre_approval_expiry
    ):
        raise ValueError("buyer authorization is outside its signing validity window")
    typed_data = receive_authorization_typed_data(terms, domain)
    try:
        raw = (
            bytes.fromhex(signature.removeprefix("0x"))
            if isinstance(signature, str)
            else bytes(signature)
        )
        if len(raw) != 65 or raw[64] not in (27, 28):
            raise ValueError
        if not 0 < int.from_bytes(raw[32:64]) <= SECP256K1_HALF_ORDER:
            raise ValueError
        recovered = Account.recover_message(
            encode_typed_data(full_message=typed_data), signature=raw
        )
    except Exception:
        raise ValueError("invalid EOA buyer authorization signature") from None
    if recovered.lower() != terms.payment_info.payer.lower():
        raise ValueError("buyer signature does not authorize the accepted payer and payment terms")
    return raw
