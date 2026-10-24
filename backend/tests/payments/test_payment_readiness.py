"""Readiness fault injection: synthetic keys/RPC, temporary journals, no network."""

import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_base_transport import buyer_signature, lab
from test_payment_lab import invoke

from app.payments import journal as journal_module
from app.payments.attempt import PaymentAttempt
from app.payments.base import BasePaymentTransport
from app.payments.journal import PaymentJournal

# isort: split
from spikes.payments.offline import BUYER_KEY, OfflineRpc, offline_config


@pytest.mark.parametrize("state", ["reserved", "signed"])
def test_reconcile_unsubmitted_operation_returns_pending(tmp_path, state):
    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    journal = PaymentJournal(tmp_path / "lab.sqlite3")
    with journal.transaction() as db:
        payment = journal.payment(db, "capture-a")
        operation = lab.operation_for(payment, "fund")
        journal.reserve(db, operation)
        if state == "signed":
            nonce = journal.reserve_nonce(
                db, operation.operation_id, payment.terms.payment_info.operator, 0
            )
    if state == "signed":
        transport = BasePaymentTransport(offline_config(journal.path, signing=True), rpc=rpc)
        signed = transport.prepare_transaction(
            "fund", payment.terms, nonce, buyer_signature(payment.terms)
        )
        with journal.transaction() as db:
            journal.save_signed(db, operation.operation_id, signed)
    assert invoke(tmp_path, "reconcile", rpc=rpc) == 3
    _, operations = lab.read_payment(journal.path, "capture-a")
    assert operations[0].state == state
    assert not rpc.broadcasts


def test_multi_read_latency_expires_lease_without_send_and_preserves_nonce(tmp_path, monkeypatch):
    class Clock:
        elapsed = 0

        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 24, tzinfo=UTC) + timedelta(seconds=cls.elapsed)

    class SlowRpc(OfflineRpc):
        delay = 0

        def request(self, method, params):
            Clock.elapsed += self.delay
            return super().request(method, params)

    monkeypatch.setattr(journal_module, "datetime", Clock)
    # Retain the historical fencing reproduction with cooperative renewal unavailable.
    # Chain time deliberately stays fixed here; progressing chain/window cases live in
    # test_lease_renewal.py. A stalled checkpoint schedule cannot revive an expired lease.
    monkeypatch.setattr("app.payments.attempt.RENEW_SECONDS", 1000)
    monkeypatch.setattr(lab, "PaymentAttempt", lambda: PaymentAttempt(clock=lambda: Clock.elapsed))
    rpc = SlowRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    path = tmp_path / "lab.sqlite3"
    original, _ = lab.read_payment(path, "capture-a")
    rpc.delay = 4  # Every read succeeds below the 15s HTTP timeout; no wall-clock sleep.
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 3
    payment, operations = lab.read_payment(path, "capture-a")
    operation = operations[0]
    assert payment.terms == original.terms
    assert payment.state == "awaiting_signature"
    assert operation.state == "reserved" and operation.nonce == 0
    assert operation.transaction_hash is None
    assert Clock.elapsed > 120 and not rpc.broadcasts
    with PaymentJournal(path).transaction() as db:
        assert PaymentJournal.private(db, operation.operation_id)[0] is None
    # Inspection cannot disguise this as a completed operation or send it.
    assert invoke(tmp_path, "reconcile", rpc=rpc) == 3
    # Faster RPC can resume this never-submitted reservation with its original nonce.
    rpc.delay = 0
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 0
    payment, resumed = lab.read_payment(path, "capture-a")
    assert payment.terms == original.terms
    assert resumed[0].operation_id == operation.operation_id
    assert resumed[0].nonce == operation.nonce
    assert resumed[0].state == "submitted" and len(rpc.broadcasts) == 1


def test_crash_after_submitted_commit_stays_pending_without_rebroadcast(tmp_path, monkeypatch):
    class ProcessCrash(BaseException):
        pass

    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    path = tmp_path / "lab.sqlite3"

    def crash_before_send(self, raw_transaction, explicit_testnet_broadcast=False):
        payment, operations = lab.read_payment(path, "capture-a")
        assert payment.state == "funding_pending"
        assert operations[0].state == "submitted"
        with PaymentJournal(path).transaction() as db:
            assert PaymentJournal.private(db, operations[0].operation_id)[0] == raw_transaction
        raise ProcessCrash

    with monkeypatch.context() as patch:
        patch.setattr(BasePaymentTransport, "broadcast", crash_before_send)
        with pytest.raises(ProcessCrash):
            invoke(tmp_path, "fund", "--simulate", rpc=rpc)
    original, operations = lab.read_payment(path, "capture-a")
    operation = operations[0]
    with PaymentJournal(path).transaction() as db:
        saved = PaymentJournal.private(db, operation.operation_id)
    assert saved[0] is not None and not rpc.broadcasts
    # Disable example-only chain reconstruction. Otherwise saved submitted bytes are
    # synthetically mined on restart, hiding exactly the real recovery gap under test.
    rpc.mine = lambda raw: operation.transaction_hash
    monkeypatch.setattr(
        BasePaymentTransport, "prepare_transaction", lambda *a, **k: pytest.fail("re-signed")
    )
    for command, flags in (("reconcile", ()), ("fund", ("--simulate",)), ("reconcile", ())):
        assert invoke(tmp_path, command, *flags, rpc=rpc) == 3
    payment, resumed = lab.read_payment(path, "capture-a")
    assert payment.terms == original.terms
    assert payment.state == "funding_pending"
    assert len(resumed) == 1 and resumed[0].state == "submitted"
    assert resumed[0].transaction_hash == operation.transaction_hash
    assert resumed[0].nonce == operation.nonce
    with PaymentJournal(path).transaction() as db:
        assert PaymentJournal.private(db, operation.operation_id) == saved
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
    assert not rpc.broadcasts and not rpc.receipts


@pytest.mark.parametrize(
    "probe", ["public", "provider", "generic_error", "wrong_sender", "timeout"]
)
def test_documented_read_only_probes_fail_closed_without_keys(tmp_path, monkeypatch, probe, capsys):
    """Validate copyable recipes, not EVM authority: every response below is injected."""
    from eth_abi import encode
    from eth_account import Account
    from eth_utils import keccak

    config = offline_config(tmp_path / "probe.sqlite3")
    rpc = OfflineRpc()
    payer = Account.from_key(BUYER_KEY).address

    class PublicOnly(dict):
        def get(self, key, default=None):
            if "PRIVATE_KEY" in key:
                pytest.fail("read-only recipe accessed signing configuration")
            return super().get(key, default)

    monkeypatch.setattr(
        os,
        "environ",
        PublicOnly(
            BASE_OPERATOR_ADDRESS=config.operator_address,
            SPIKE_BUYER_ADDRESS=payer,
            BASE_PROVIDER_ADDRESS=config.provider_address,
            PAYMENT_JOURNAL_PATH=str(config.journal_path),
            ENABLE_TESTNET_BROADCAST="false",
        ),
    )
    monkeypatch.setattr(
        "app.payments.base.BasePaymentTransport",
        lambda config: BasePaymentTransport(config, rpc=rpc),
    )
    before = None
    if probe != "public":
        # Populate a fresh temporary *injected-chain* fixture. No live obligation exists.
        payment = lab.create_fixture(config, "live-capture-a-20261024", payer, 1000, 3600)
        transport = BasePaymentTransport(offline_config(config.journal_path, signing=True), rpc=rpc)
        signed = transport.prepare_transaction(
            "fund", payment.terms, 0, buyer_signature(payment.terms)
        )
        rpc.mine(signed.raw_transaction)
        with PaymentJournal(config.journal_path).transaction() as db:
            PaymentJournal.create_payment(db, payment.model_copy(update={"state": "funded"}))
        before = Path(config.journal_path).read_bytes()

    class ProviderResponse:
        def __init__(self, *args, **kwargs):
            pass

        def make_request(self, method, params):
            assert method == "eth_call" and params[1]["requireCanonical"] is True
            if params[0]["from"].lower() == config.operator_address.lower():
                return {"result": "0x"}
            if probe == "timeout":
                raise TimeoutError("secret-provider-url")
            if probe == "generic_error":
                return {"error": {"message": "secret-provider-url"}}
            sender = payer if probe == "wrong_sender" else config.provider_address
            data = keccak(text="InvalidSender(address,address)")[:4] + encode(
                ["address", "address"], [sender, config.operator_address]
            )
            return {"error": {"data": "0x" + data.hex()}}

    monkeypatch.setattr("web3.HTTPProvider", ProviderResponse)
    handoff = Path(__file__).parents[3] / "docs/workstreams/07-payment-readiness.md"
    recipes = re.findall(
        r"backend/\.venv/bin/python - <<'PY'\n(.*?)\nPY", handoff.read_text(), re.S
    )
    assert len(recipes) == 2
    source = recipes[0 if probe == "public" else 1]
    if probe in ("generic_error", "wrong_sender", "timeout"):
        with pytest.raises(SystemExit, match="inconclusive/failed"):
            exec(compile(source, str(handoff), "exec"), {})
    else:
        exec(compile(source, str(handoff), "exec"), {})
    output = capsys.readouterr()
    assert "secret-provider-url" not in output.out + output.err
    assert not rpc.broadcasts
    assert not any(method == "eth_sendRawTransaction" for method, _ in rpc.calls)
    if before is None:
        assert not list(tmp_path.iterdir())
    else:
        assert Path(config.journal_path).read_bytes() == before
