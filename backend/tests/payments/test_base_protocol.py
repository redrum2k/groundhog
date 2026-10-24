"""Offline synthetic fixtures only; these tests make no chain or network calls."""

import hashlib
import json
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data, hash_domain
from eth_utils import keccak
from pydantic import ValidationError

from app.contracts.models import Money
from app.contracts.payments import AuthorizationTypedData, PaymentInfo, PaymentTerms
from app.payments.base_config import (
    BASE_COLLECTOR_ADDRESS,
    BASE_ESCROW_ADDRESS,
    BASE_USDC_ADDRESS,
    BasePaymentConfig,
)
from app.payments.protocol import (
    PAYMENT_INFO_TYPE,
    compute_authorization_nonce,
    compute_payment_hash,
    receive_authorization_typed_data,
    usdc_domain,
    verify_buyer_signature,
    verify_domain_separator,
)

# Published synthetic scalars; not real wallet credentials.
BUYER = Account.from_key(bytes.fromhex("11" * 32))
OPERATOR = Account.from_key(bytes.fromhex("22" * 32))
PROVIDER = Account.from_key(bytes.fromhex("33" * 32))
OTHER = Account.from_key(bytes.fromhex("44" * 32))
DOMAIN = usdc_domain("USDC")


def info(**changes):
    values = dict(
        operator=OPERATOR.address,
        payer=BUYER.address,
        receiver=PROVIDER.address,
        token=BASE_USDC_ADDRESS,
        max_amount=100000,
        pre_approval_expiry=200,
        authorization_expiry=400,
        refund_expiry=600,
        fee_receiver=OPERATOR.address,
        salt=2**200 + 41,
    )
    values.update(changes)
    return PaymentInfo(**values)


def terms(payment_info=None, **changes):
    payment_info = payment_info or info()
    values = dict(
        payment_id="payment_test",
        mode="base_sepolia",
        asset_address=payment_info.token,
        amount_atomic=payment_info.max_amount,
        payment_info=payment_info,
        escrow_address=BASE_ESCROW_ADDRESS,
        collector_address=BASE_COLLECTOR_ADDRESS,
        payment_hash=compute_payment_hash(payment_info),
        authorization_nonce=compute_authorization_nonce(payment_info),
        pricing_rule="catalog-usd-usdc-1to1-v1",
        display_amount=Money(
            amount_minor=payment_info.max_amount // 10000, currency="USD", decimals=2
        ),
        settlement_terms="Synthetic test USDC terms",
    )
    values.update(changes)
    return PaymentTerms(**values)


def sign(accepted, domain=DOMAIN):
    message = encode_typed_data(full_message=receive_authorization_typed_data(accepted, domain))
    return BUYER.sign_message(message).signature


def test_hash_matches_independently_padded_solidity_words_and_distinct_nonce():
    accepted = info()
    words = [keccak(text=PAYMENT_INFO_TYPE)]
    for value in accepted.to_contract_tuple():
        number = int(value, 16) if isinstance(value, str) else value
        words.append(number.to_bytes(32))
    inner = keccak(b"".join(words))
    expected = keccak((84532).to_bytes(32) + int(BASE_ESCROW_ADDRESS, 16).to_bytes(32) + inner)
    assert compute_payment_hash(accepted) == "0x" + expected.hex()
    assert compute_payment_hash(accepted) != compute_authorization_nonce(accepted)
    changed_payer = info(payer=OTHER.address)
    assert compute_payment_hash(accepted) != compute_payment_hash(changed_payer)
    assert compute_authorization_nonce(accepted) == compute_authorization_nonce(changed_payer)
    assert accepted.payer == BUYER.address
    assert compute_payment_hash(accepted, 1) != compute_payment_hash(accepted)
    assert compute_payment_hash(accepted, escrow_address=OTHER.address) != compute_payment_hash(
        accepted
    )


def test_typed_data_has_collector_full_amount_payer_agnostic_nonce_and_exact_uints():
    accepted = terms()
    data = receive_authorization_typed_data(accepted, DOMAIN)
    assert data["primaryType"] == "ReceiveWithAuthorization"
    assert data["domain"]["chainId"] == 84532
    assert data["message"] == {
        "from": BUYER.address,
        "to": BASE_COLLECTOR_ADDRESS,
        "value": "100000",
        "validAfter": "0",
        "validBefore": "200",
        "nonce": accepted.authorization_nonce,
    }
    assert accepted.model_dump(mode="json")["payment_info"]["salt"] == str(2**200 + 41)
    assert "signature" not in json.dumps(data)
    signature = sign(accepted)
    assert verify_buyer_signature(accepted, DOMAIN, signature, 100) == bytes(signature)
    assert len(signature) == 65
    assert signature[-1] in (27, 28)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operator", OTHER.address),
        ("receiver", OTHER.address),
        ("max_amount", 200000),
        ("pre_approval_expiry", 201),
        ("authorization_expiry", 401),
        ("refund_expiry", 601),
        ("fee_receiver", OTHER.address),
        ("salt", 999),
    ],
)
def test_signature_binds_every_accepted_payment_field(field, value):
    original = terms()
    signature = sign(original)
    changed = terms(info(**{field: value}))
    with pytest.raises(ValueError, match="accepted payer and payment terms"):
        verify_buyer_signature(changed, DOMAIN, signature, 100)


@pytest.mark.parametrize("now", [0, 200, 201, True, 100.5])
def test_signature_rejects_expired_or_invalid_window(now):
    accepted = terms()
    with pytest.raises(ValueError, match="validity window"):
        verify_buyer_signature(accepted, DOMAIN, sign(accepted), now)


def test_signature_rejects_wrong_signer_malformed_or_account_abstraction():
    accepted = terms()
    data = encode_typed_data(full_message=receive_authorization_typed_data(accepted, DOMAIN))
    with pytest.raises(ValueError, match="accepted payer"):
        verify_buyer_signature(accepted, DOMAIN, OTHER.sign_message(data).signature, 100)
    for signature in ("bad", b"", b"x" * 64, b"x" * 96, b"x" * 65):
        with pytest.raises(ValueError, match="invalid EOA"):
            verify_buyer_signature(accepted, DOMAIN, signature, 100)


@pytest.mark.parametrize(
    "changes",
    [{"chainId": 1}, {"verifyingContract": OTHER.address}, {"version": "1"}, {"extra": "no"}],
)
def test_domain_substitution_rejected(changes):
    with pytest.raises(ValueError, match="domain"):
        receive_authorization_typed_data(terms(), dict(DOMAIN, **changes))


def test_domain_name_must_match_signature_and_observed_separator():
    accepted = terms()
    other_domain = usdc_domain("Wrong name")
    with pytest.raises(ValueError, match="accepted payer"):
        verify_buyer_signature(accepted, other_domain, sign(accepted), 100)
    observed = hash_domain(DOMAIN)
    verify_domain_separator(DOMAIN, observed)
    verify_domain_separator(DOMAIN, "0x" + observed.hex())
    with pytest.raises(ValueError, match="DOMAIN_SEPARATOR"):
        verify_domain_separator(other_domain, observed)


@pytest.mark.parametrize(
    "changes",
    [
        {"payment_hash": "0x" + "ab" * 32},
        {"authorization_nonce": "0x" + "ab" * 32},
        {"escrow_address": OTHER.address},
        {"collector_address": OTHER.address},
    ],
)
def test_stale_hash_or_deployment_substitution_rejected(changes):
    with pytest.raises(ValueError):
        receive_authorization_typed_data(terms(**changes), DOMAIN)


def test_contract_rejects_non_exact_amounts_and_invalid_deadlines():
    for amount in (0.1, True, "000100000", 2**120):
        with pytest.raises(ValidationError):
            info(max_amount=amount)
    with pytest.raises(ValidationError):
        info(pre_approval_expiry=500)
    with pytest.raises(ValidationError):
        terms(amount_atomic=200000)


def test_config_does_not_use_unrelated_credentials_or_enable_broadcast_by_default():
    config = BasePaymentConfig.from_env({"CDP_API_KEY_SECRET": "unrelated-secret"})
    assert config.operator_address is None
    assert config.enable_testnet_broadcast is False
    redacted = BasePaymentConfig(
        rpc_url="https://private.invalid/key", operator_private_key="secret"
    )
    assert "secret" not in repr(redacted)
    assert "private.invalid" not in repr(redacted)
    with pytest.raises(ValueError, match="84532"):
        BasePaymentConfig(chain_id=1)
    with pytest.raises(ValueError, match="at least 2"):
        BasePaymentConfig(confirmations=1)


def test_pinned_source_and_interface_hashes_are_intact():
    folder = Path(__file__).parents[2] / "app" / "payments" / "abi"
    provenance = json.loads((folder / "provenance.json").read_text())
    assert provenance["commit"] == "b748fdd7a830a655a19a530edcf2a94b9dc7d25f"
    for group in ("source_sha256", "abi_sha256"):
        for relative, expected in provenance[group].items():
            assert hashlib.sha256((folder / relative).read_bytes()).hexdigest() == expected
    abi = json.loads((folder / "AuthCaptureEscrow.json").read_text())
    capture = next(item for item in abi if item.get("name") == "capture")
    assert capture["inputs"][2] == {"name": "feeAmount", "type": "uint256"}


def test_frontend_typed_schema_round_trip_preserves_wallet_message():
    accepted = terms()
    original = receive_authorization_typed_data(accepted, DOMAIN)
    schema = AuthorizationTypedData.model_validate(original)
    wire = schema.model_dump(mode="json")
    assert wire == original
    assert "from" in wire["message"]
    assert "from_" not in wire["message"]
    assert type(wire["message"]["value"]) is str
    assert type(wire["domain"]["chainId"]) is int
    assert encode_typed_data(full_message=wire) == encode_typed_data(full_message=original)
    signature = BUYER.sign_message(encode_typed_data(full_message=wire)).signature
    assert verify_buyer_signature(accepted, wire["domain"], signature, 100) == bytes(signature)
