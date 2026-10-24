"""No live RPC: wire-level vectors, hostile evidence, and real outbox restart tests."""

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
import rlp
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_keys import keys
from eth_utils import keccak
from web3 import Web3

from app.payments.base import BasePaymentTransport
from app.payments.base_config import BASE_ESCROW_ADDRESS, BASE_USDC_ADDRESS, BasePaymentConfig
from app.payments.base_rpc import BaseTransportError, HttpRpc
from app.payments.journal import PaymentJournal
from app.payments.protocol import (
    compute_authorization_nonce,
    compute_payment_hash,
    receive_authorization_typed_data,
    usdc_domain,
)

# Load the CLI by path as users do; it adds the repository's lab package to sys.path.
RUNNER = Path(__file__).parents[3] / "spikes/payments/run.py"
spec = importlib.util.spec_from_file_location("payment_lab_run", RUNNER)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

from spikes.payments.offline import (  # noqa: E402
    BUYER_KEY,
    STORE,
    OfflineRpc,
    offline_config,
)


@pytest.fixture
def setup(tmp_path):
    config = offline_config(tmp_path / "lab.sqlite3", signing=True)
    rpc = OfflineRpc()
    payment = lab.create_fixture(
        config, "vector-a", Account.from_key(BUYER_KEY).address, 1000, 3600, offline=True
    )
    info = payment.terms.payment_info.model_copy(update={"salt": 41})
    terms = payment.terms.model_copy(
        update={
            "payment_info": info,
            "payment_hash": compute_payment_hash(info),
            "authorization_nonce": compute_authorization_nonce(info),
        }
    )
    payment = payment.model_copy(update={"terms": terms})
    transport = BasePaymentTransport(config, rpc=rpc)
    return config, rpc, payment, transport


def buyer_signature(terms):
    typed = receive_authorization_typed_data(terms, usdc_domain("USDC"))
    return bytes(
        Account.from_key(BUYER_KEY).sign_message(encode_typed_data(full_message=typed)).signature
    )


def funded(setup):
    _, rpc, payment, transport = setup
    signed = transport.prepare_transaction("fund", payment.terms, 7, buyer_signature(payment.terms))
    assert transport.broadcast(signed.raw_transaction, True) == signed.transaction_hash
    return signed


def test_import_and_constructor_are_inert(setup, monkeypatch):
    config, rpc, _, _ = setup
    rpc.calls.clear()
    BasePaymentTransport(config, rpc=rpc)
    assert rpc.calls == []
    monkeypatch.setattr("os.getenv", lambda *a, **k: pytest.fail("environment read"))
    import app.payments.base as module

    importlib.reload(module)
    assert rpc.calls == []


def test_domain_and_preflight_are_read_only_pinned_and_key_free(setup):
    config, rpc, payment, _ = setup
    transport = BasePaymentTransport(replace(config, operator_private_key=None), rpc=rpc)
    assert transport.verified_usdc_domain() == usdc_domain("USDC")
    result = transport.preflight(payment.terms, action="fund")
    assert result["amount_atomic"] == "100000"
    assert result["token_store"].lower() == STORE.lower()
    assert result["payment_state"] == (False, 0, 0)
    assert not rpc.broadcasts
    for method, params in rpc.calls:
        if method in ("eth_call", "eth_getCode", "eth_getBalance"):
            assert params[1] == {"blockHash": rpc.block(101)["hash"], "requireCanonical": True}


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("chain_id", 1, "chain"),
        ("separator", b"\xff" * 32, "DOMAIN_SEPARATOR"),
        ("decimals", 18, "six decimals"),
        ("collector_escrow", "0x" + "99" * 20, "another escrow"),
        ("code_missing", BASE_ESCROW_ADDRESS, "interface selectors"),
        ("code_missing", BASE_USDC_ADDRESS, "deployed code"),
        ("used", True, "used"),
        ("gas_balance", 0, "ETH"),
    ],
)
def test_preflight_fails_closed(setup, field, value, match):
    _, rpc, payment, transport = setup
    setattr(rpc, field, value)
    with pytest.raises(ValueError, match=match):
        transport.preflight(payment.terms, action="fund")
    assert not rpc.broadcasts


def test_wrong_terms_and_configuration_rejected_before_signing(setup):
    config, rpc, payment, transport = setup
    with pytest.raises(ValueError, match="mock"):
        transport.preflight(payment.terms.model_copy(update={"mode": "mock"}))
    for changes in (
        {"provider_address": Account.from_key(BUYER_KEY).address},
        {"operator_private_key": BUYER_KEY, "operator_public_address": None},
    ):
        with pytest.raises(ValueError, match="differs"):
            BasePaymentTransport(replace(config, **changes), rpc=rpc).preflight(payment.terms)
    rpc.balances[payment.terms.payment_info.payer.lower()] = 99999
    with pytest.raises(ValueError, match="sufficient buyer"):
        transport.preflight(payment.terms, action="fund")
    with pytest.raises(ValueError, match="pinned"):
        BasePaymentConfig(escrow_address="0x" + "99" * 20)
    with pytest.raises(ValueError, match="84532"):
        BasePaymentConfig(chain_id=1)


def test_exact_calldata_against_solidity_words_and_independent_web3_codec(setup):
    _, _, payment, transport = setup
    terms = payment.terms
    sig = buyer_signature(terms)
    values = terms.payment_info.to_contract_tuple()
    words = b"".join((int(v, 16) if isinstance(v, str) else v).to_bytes(32) for v in values)
    declaration = (
        "(address,address,address,address,uint120,uint48,"
        "uint48,uint48,uint16,uint16,address,uint256)"
    )
    expected = keccak(text=f"authorize({declaration},uint256,address,bytes)")[:4]
    expected += words + (100000).to_bytes(32) + int(terms.collector_address, 16).to_bytes(32)
    expected += (15 * 32).to_bytes(32) + (65).to_bytes(32) + sig + b"\0" * 31
    assert transport.calldata("fund", terms, sig) == "0x" + expected.hex()
    abi = json.loads(
        (Path(__file__).parents[2] / "app/payments/abi/AuthCaptureEscrow.json").read_text()
    )
    contract = Web3().eth.contract(abi=abi)
    for action, name, args in (
        ("fund", "authorize", [values, 100000, terms.collector_address, sig]),
        ("capture", "capture", [values, 100000, 0, terms.payment_info.fee_receiver]),
        ("void", "void", [values]),
        ("reclaim", "reclaim", [values]),
    ):
        assert transport.calldata(action, terms, sig) == contract.encode_abi(name, args=args)
    assert transport.calldata("capture", terms)[-128:] == (
        "0" * 64 + int(terms.payment_info.fee_receiver, 16).to_bytes(32).hex()
    )


def test_type2_signing_manual_rlp_recovery_and_determinism(setup):
    config, rpc, payment, transport = setup
    sig = buyer_signature(payment.terms)
    signed = transport.prepare_transaction("fund", payment.terms, 7, sig)
    assert signed == transport.prepare_transaction("fund", payment.terms, 7, sig)
    raw = signed.raw_transaction
    assert raw[0] == 2
    fields = rlp.decode(raw[1:])
    assert len(fields) == 12
    assert [int.from_bytes(v) for v in fields[:5]] == [84532, 7, 1000000, 3000000, 180000]
    assert fields[5] == bytes.fromhex(BASE_ESCROW_ADDRESS[2:])
    assert int.from_bytes(fields[6]) == 0
    digest = keccak(b"\x02" + rlp.encode(fields[:9]))
    signature = keys.Signature(vrs=tuple(int.from_bytes(v) for v in fields[9:]))
    assert (
        signature.recover_public_key_from_msg_hash(digest).to_checksum_address()
        == config.operator_address
    )
    assert signed.transaction_hash == "0x" + keccak(raw).hex()
    assert signed.sender == config.operator_address and signed.nonce == 7
    assert not rpc.broadcasts
    assert all(method != "eth_getTransactionCount" for method, _ in rpc.calls)
    # Fixed vector uses synthetic scalars 0x11/0x22, salt 41, time 1000 and nonce 7.
    assert sig.hex() == SIGNATURE_VECTOR
    assert signed.transaction_hash == TRANSACTION_HASH_VECTOR
    domain = keccak(
        keccak(
            text=(
                "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
            )
        )
        + keccak(text="USDC")
        + keccak(text="2")
        + (84532).to_bytes(32)
        + int(BASE_USDC_ADDRESS, 16).to_bytes(32)
    )
    terms = payment.terms
    message = keccak(
        keccak(
            text=(
                "ReceiveWithAuthorization(address from,address to,uint256 value,"
                "uint256 validAfter,uint256 validBefore,bytes32 nonce)"
            )
        )
        + int(terms.payment_info.payer, 16).to_bytes(32)
        + int(terms.collector_address, 16).to_bytes(32)
        + (100000).to_bytes(32)
        + (0).to_bytes(32)
        + (1300).to_bytes(32)
        + bytes.fromhex(terms.authorization_nonce[2:])
    )
    recovered = keys.Signature(
        vrs=(sig[64] - 27, int.from_bytes(sig[:32]), int.from_bytes(sig[32:64]))
    )
    assert (
        recovered.recover_public_key_from_msg_hash(
            keccak(b"\x19\x01" + domain + message)
        ).to_checksum_address()
        == terms.payment_info.payer
    )


SIGNATURE_VECTOR = (
    "0d3056dc6b6d9e68a21b58b050f76ca41f189e2c988176ce0c2476cececb80d2"
    "152cc5b6f825d770d0dc3b4f699d342620c86c4db21a36f813d2de0acae2cf271c"
)
TRANSACTION_HASH_VECTOR = "0x6fbc8a33f6288fd080658da68211b9c98a25d652e1bdfeab1415b130dc5d3d08"


def test_broadcast_double_optin_and_no_retry(setup):
    config, rpc, payment, transport = setup
    signed = transport.prepare_transaction("fund", payment.terms, 7, buyer_signature(payment.terms))
    for enabled, explicit in ((False, False), (False, True), (True, False)):
        adapter = BasePaymentTransport(replace(config, enable_testnet_broadcast=enabled), rpc=rpc)
        with pytest.raises(ValueError, match="opt-in"):
            adapter.broadcast(signed.raw_transaction, explicit)
    assert not rpc.broadcasts
    rpc.raise_after_send = True
    with pytest.raises(ValueError, match="reconcile"):
        transport.broadcast(signed.raw_transaction, True)
    assert rpc.broadcasts == [signed.raw_transaction]
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "confirmed"
    assert rpc.broadcasts == [signed.raw_transaction]


@pytest.mark.parametrize("action", ["capture", "void", "reclaim"])
def test_exact_funding_then_full_terminal_reconciliation(setup, action):
    _, rpc, payment, transport = setup
    funding = funded(setup)
    observation = transport.reconcile("fund", payment.terms, funding.transaction_hash)
    assert observation.status == "confirmed"
    assert observation.payment_state["capturable_amount"] == 100000
    assert observation.payment_state["refundable_amount"] == 0
    if action == "reclaim":
        with pytest.raises(ValueError, match="payer nonce"):
            transport.prepare_transaction(action, payment.terms, 8)
        rpc.timestamp = payment.terms.payment_info.authorization_expiry
        request = transport.transaction_request(action, payment.terms, 8)
        assert request["from"].lower() == payment.terms.payment_info.payer.lower()
        signed = Account.sign_transaction(request, BUYER_KEY)
        tx_hash = rpc.mine(bytes(signed.raw_transaction))
    else:
        signed = transport.prepare_transaction(action, payment.terms, 8)
        tx_hash = transport.broadcast(signed.raw_transaction, True)
    result = transport.reconcile(action, payment.terms, tx_hash)
    assert result.status == "confirmed"
    assert result.event["amount_atomic"] == 100000
    assert result.payment_state["capturable_amount"] == 0
    assert result.payment_state["refundable_amount"] == (100000 if action == "capture" else 0)
    assert result.payment_state["provider_balance"] == (100000 if action == "capture" else 0)
    assert result.payment_state["buyer_balance"] == (
        10**9 - 100000 if action == "capture" else 10**9
    )
    assert (
        transport.reconcile("fund", payment.terms, funding.transaction_hash).status == "uncertain"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "amount",
        "info",
        "event",
        "emitter",
        "duplicate",
        "removed",
        "block",
        "state",
        "sender",
        "input",
        "chain",
        "custody",
    ],
)
def test_receipt_conflicts_never_confirm(setup, mutation):
    _, rpc, payment, transport = setup
    signed = funded(setup)
    receipt = rpc.receipts[signed.transaction_hash]
    log = receipt["logs"][0]
    if mutation == "hash":
        log["topics"][1] = "0x" + "99" * 32
    elif mutation in ("amount", "info"):
        raw = bytearray.fromhex(log["data"][2:])
        raw[(12 if mutation == "amount" else 11) * 32 + 31] ^= 1
        log["data"] = "0x" + raw.hex()
    elif mutation == "event":
        log["topics"][0] = "0x" + keccak(text="PaymentVoided(bytes32,uint256)").hex()
    elif mutation == "emitter":
        log["address"] = STORE
    elif mutation == "duplicate":
        receipt["logs"].append(dict(log))
    elif mutation == "removed":
        log["removed"] = True
    elif mutation == "block":
        log["blockHash"] = "0x" + "99" * 32
    elif mutation == "state":
        rpc.states[payment.terms.payment_hash] = (True, 0, 100000)
    elif mutation == "sender":
        rpc.transactions[signed.transaction_hash]["from"] = payment.terms.payment_info.receiver
    elif mutation == "input":
        rpc.transactions[signed.transaction_hash]["input"] = transport.calldata(
            "void", payment.terms
        )
    elif mutation == "chain":
        rpc.chain_id = 1
    elif mutation == "custody":
        rpc.balances[STORE.lower()] = 0
        rpc.historical_balances[receipt["blockHash"]][STORE.lower()] = 0
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "uncertain"


def test_failed_pending_missing_and_orphaned_receipts(setup):
    _, rpc, payment, transport = setup
    signed = funded(setup)
    receipt = rpc.receipts[signed.transaction_hash]
    rpc.height -= 1
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "pending"
    receipt["status"] = "0x0"
    receipt["logs"] = []
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "pending"
    rpc.height += 1
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "failed"
    rpc.orphan = True
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "orphaned"
    del rpc.receipts[signed.transaction_hash]
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "pending"
    assert len(rpc.broadcasts) == 1


def test_capture_fee_and_wrong_return_amount_rejected(setup):
    _, rpc, payment, transport = setup
    funded(setup)
    signed = transport.prepare_transaction("capture", payment.terms, 8)
    transport.broadcast(signed.raw_transaction, True)
    log = rpc.receipts[signed.transaction_hash]["logs"][0]
    log["data"] = (
        "0x"
        + encode(
            ["uint256", "uint256", "address"], [100000, 1, payment.terms.payment_info.fee_receiver]
        ).hex()
    )
    assert (
        transport.reconcile("capture", payment.terms, signed.transaction_hash).status == "uncertain"
    )


def test_deadline_and_gas_bounds_prevent_signing(setup):
    config, rpc, payment, transport = setup
    funded(setup)
    with pytest.raises(ValueError, match="expired capture"):
        transport.transaction_request("reclaim", payment.terms, 8)
    rpc.timestamp = payment.terms.payment_info.authorization_expiry
    with pytest.raises(ValueError, match="expired"):
        transport.prepare_transaction("capture", payment.terms, 8)
    transport.transaction_request("void", payment.terms, 8)
    bounded = BasePaymentTransport(replace(config, max_gas=21000), rpc=rpc)
    with pytest.raises(ValueError, match="gas"):
        bounded.prepare_transaction("void", payment.terms, 8)


def test_outbox_restart_timeout_and_terminal_idempotency_use_same_bytes(setup):
    config, rpc, payment, transport = setup
    journal = PaymentJournal(config.journal_path)
    operation = lab.operation_for(payment, "fund")
    with journal.transaction() as db:
        journal.create_payment(db, payment)
        journal.reserve(db, operation, "0x" + buyer_signature(payment.terms).hex())
    rpc.raise_after_send = True
    executor = lab.laboratory_executor(journal, transport)
    uncertain = executor.run_one(operation.operation_id, broadcast=True)
    assert uncertain.state == "uncertain"
    with journal.transaction() as db:
        original_raw = journal.private(db, operation.operation_id)[0]
        assert original_raw == rpc.broadcasts[0]
    restarted = PaymentJournal(config.journal_path)
    executor = lab.laboratory_executor(restarted, BasePaymentTransport(config, rpc=rpc))
    confirmed = executor.run_one(operation.operation_id, broadcast=True)
    assert confirmed.state == "confirmed"
    assert confirmed.nonce == uncertain.nonce
    assert confirmed.transaction_hash == uncertain.transaction_hash
    assert len(rpc.broadcasts) == 1
    terminal = lab.operation_for(payment, "void")
    with restarted.transaction() as db:
        restarted.reserve(db, terminal)
    rpc.raise_after_send = False
    assert executor.run_one(terminal.operation_id, broadcast=True).state == "submitted"
    assert executor.run_one(terminal.operation_id).state == "confirmed"
    assert executor.run_one(terminal.operation_id, broadcast=True).state == "confirmed"
    with restarted.transaction() as db:
        assert restarted.payment_terms(db, payment.payment_id) == payment.terms
        assert restarted.payment(db, payment.payment_id).state == "voided"
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 2
    assert len(rpc.broadcasts) == 2


def test_http_provider_no_retry_and_redaction(monkeypatch):
    rpc = HttpRpc("https://rpc.invalid/secret-key")
    assert rpc._provider.exception_retry_configuration is None
    calls = []

    def failure(*args):
        calls.append(args)
        raise RuntimeError("https://rpc.invalid/secret-key raw-private-capability")

    monkeypatch.setattr(rpc._provider, "make_request", failure)
    with pytest.raises(BaseTransportError) as error:
        rpc.request("eth_sendRawTransaction", ["raw-private-capability"])
    assert len(calls) == 1
    assert "secret-key" not in str(error.value)
    assert "capability" not in str(error.value)
    assert error.value.__suppress_context__


def test_no_credential_lookup_for_inspection_and_redacted_invalid_config():
    class PublicOnly(dict):
        def get(self, key, default=None):
            if "PRIVATE_KEY" in key:
                pytest.fail("inspection read signing credentials")
            return super().get(key, default)

    config = BasePaymentConfig.from_env(PublicOnly(), include_signer=False)
    assert config.operator_address is None
    with pytest.raises(ValueError) as error:
        BasePaymentConfig.from_env({"BASE_CHAIN_ID": "super-secret"})
    assert "super-secret" not in str(error.value)
    assert "BASE_CHAIN_ID" in str(error.value)


def test_wrong_chain_sender_and_reclaim_cannot_use_operator_broadcast(setup):
    _, rpc, payment, transport = setup
    funded(setup)
    rpc.timestamp = payment.terms.payment_info.authorization_expiry
    request = transport.transaction_request("reclaim", payment.terms, 0)
    payer_signed = Account.sign_transaction(request, BUYER_KEY)
    with pytest.raises(ValueError, match="allowed escrow"):
        transport.broadcast(bytes(payer_signed.raw_transaction), True)
    wrong_chain = Account.sign_transaction({**request, "chainId": 1}, BUYER_KEY)
    with pytest.raises(ValueError, match="allowed escrow"):
        transport.broadcast_reclaim(
            bytes(wrong_chain.raw_transaction), payment.terms, explicit_testnet_broadcast=True
        )
    assert len(rpc.broadcasts) == 1  # original funding only


def test_reorg_during_read_stays_uncertain(setup):
    _, rpc, payment, transport = setup
    signed = funded(setup)
    original = rpc.request
    reads = 0

    def reorg(method, params):
        nonlocal reads
        if method == "eth_getBlockByNumber" and params[0] != "latest":
            reads += 1
            if reads > 1:
                rpc.orphan = True
        return original(method, params)

    rpc.request = reorg
    assert transport.reconcile("fund", payment.terms, signed.transaction_hash).status == "uncertain"
    assert len(rpc.broadcasts) == 1
