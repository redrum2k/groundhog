"""All CLI paths use empty explicit environments, temporary journals and synthetic RPC."""

import json
import os
import subprocess
import sys

import pytest
from test_base_transport import RUNNER, lab

from app.payments.base_rpc import BaseTransportError
from app.payments.journal import PaymentJournal

# isort: split
# Importing the path-based runner above enables the repository laboratory package.
from spikes.payments.offline import BUYER_KEY, OPERATOR_KEY, OfflineRpc


def invoke(tmp_path, command, *extra, rpc=None, env=None, payment_id="capture-a"):
    return lab.main(
        [
            command,
            "--payment-id",
            payment_id,
            "--journal",
            str(tmp_path / "lab.sqlite3"),
            "--offline",
            *extra,
        ],
        env={} if env is None else env,
        rpc=rpc,
    )


@pytest.mark.parametrize("command", [None, *lab.COMMANDS])
def test_help_has_examples_and_no_rpc_or_journal(tmp_path, command):
    args = ([command] if command else []) + ["--help"]
    result = subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "Examples:" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", lab.COMMANDS)
def test_every_command_missing_configuration_is_redacted(tmp_path, capsys, command):
    code = lab.main(
        [command, "--payment-id", "missing", "--journal", str(tmp_path / "missing.sqlite3")],
        env={"BASE_OPERATOR_PRIVATE_KEY": "never-read-this-secret"},
    )
    assert code == 2
    output = capsys.readouterr()
    assert "never-read" not in output.err + output.out
    assert "BASE_SEPOLIA_RPC_URL" in output.err or "prepare" in output.err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", lab.COMMANDS)
def test_all_offline_dry_runs_do_not_sign_reserve_or_broadcast(
    tmp_path, capsys, command, monkeypatch
):
    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    capsys.readouterr()
    path = tmp_path / "lab.sqlite3"
    before = path.read_bytes()
    before_stat = path.stat().st_mtime_ns
    monkeypatch.setattr(lab.Account, "sign_transaction", lambda *a, **k: pytest.fail("signed"))
    assert invoke(tmp_path, command, "--dry-run", rpc=rpc) == 0
    output = capsys.readouterr().out
    assert "OFFLINE" in output or "offline" in output
    assert not rpc.broadcasts
    assert path.read_bytes() == before and path.stat().st_mtime_ns == before_stat
    with PaymentJournal(path).transaction() as db:
        assert PaymentJournal.operations(db, "capture-a") == ()


def test_prepare_persists_once_never_changes_salt_parties_or_deadline(tmp_path, capsys):
    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", rpc=rpc) == 0
    assert not (tmp_path / "lab.sqlite3").exists()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    payment, _ = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    rpc.timestamp += 20
    assert (
        invoke(tmp_path, "prepare", "--save-fixture", "--authorization-seconds", "1", rpc=rpc) == 0
    )
    repeated, _ = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    assert repeated.terms == payment.terms
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc, payment_id="void-b") == 0
    other, _ = lab.read_payment(tmp_path / "lab.sqlite3", "void-b")
    assert other.terms.payment_info.salt != payment.terms.payment_info.salt
    assert other.terms.payment_hash != payment.terms.payment_hash
    assert other.terms.amount_atomic == 100000
    assert (tmp_path / "lab.sqlite3").stat().st_mode & 0o777 == 0o600
    assert not rpc.broadcasts


@pytest.mark.parametrize("action", ["capture", "void", "reclaim"])
def test_cli_full_flows_and_process_restart(tmp_path, capsys, action):
    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 0
    payment, operations = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    assert payment.state == "funding_pending"
    assert operations[0].state == "submitted"
    # A new CLI invocation has a new transport and can reconstruct this explicitly
    # synthetic chain from saved signed bytes, without another signature/send.
    restarted_rpc = OfflineRpc()
    assert invoke(tmp_path, "reconcile", rpc=restarted_rpc) == 0
    if action == "reclaim":
        restarted_rpc.timestamp = payment.terms.payment_info.authorization_expiry
    assert invoke(tmp_path, action, "--simulate", rpc=restarted_rpc) == 0
    assert invoke(tmp_path, "reconcile", rpc=restarted_rpc) == 0
    assert invoke(tmp_path, action, "--simulate", rpc=restarted_rpc) == 0
    payment, operations = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    assert payment.state == ("captured" if action == "capture" else "voided")
    assert [op.state for op in operations] == ["confirmed", "confirmed"]
    assert len(restarted_rpc.broadcasts) == 1
    if action == "reclaim":
        assert operations[1].nonce == 0  # payer nonce, independent of operator's fund nonce
        with PaymentJournal(tmp_path / "lab.sqlite3").transaction() as db:
            _, _, reserved_signer = PaymentJournal.private(db, operations[1].operation_id)
        assert reserved_signer.lower() == payment.terms.payment_info.payer.lower()
    output = capsys.readouterr().out
    assert BUYER_KEY not in output and OPERATOR_KEY not in output
    assert all(op.transaction_hash not in output for op in operations)
    assert "explorer" not in output.lower()
    assert "no real receipt" in output


def test_lost_response_missing_receipt_remains_unresolved(tmp_path, capsys):
    rpc = OfflineRpc()
    invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc)
    rpc.raise_after_send = True
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 3
    _, operations = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    original = operations[0]
    rpc.receipts.clear()
    # Disable the example-only reconstruction so the actual missing-receipt transport
    # path is exercised. No signing or automatic rebroadcast is permitted.
    rpc.mine = lambda raw: original.transaction_hash
    assert invoke(tmp_path, "reconcile", rpc=rpc) == 3
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 3
    _, operations = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    assert operations[0].transaction_hash == original.transaction_hash
    assert operations[0].nonce == original.nonce
    assert len(rpc.broadcasts) == 1
    assert operations[0].state in ("submitted", "uncertain")


def test_live_optin_and_offline_fixture_promotion_are_rejected(tmp_path, capsys):
    rpc = OfflineRpc()
    invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc)
    for env in ({}, {"ENABLE_TESTNET_BROADCAST": "true"}):
        assert invoke(tmp_path, "fund", "--broadcast-testnet", rpc=rpc, env=env) == 2
    assert (
        lab.main(
            [
                "fund",
                "--payment-id",
                "capture-a",
                "--journal",
                str(tmp_path / "lab.sqlite3"),
                "--broadcast-testnet",
            ],
            env={"ENABLE_TESTNET_BROADCAST": "true"},
            rpc=rpc,
        )
        == 2
    )
    assert "offline fixture cannot become a live obligation" in capsys.readouterr().err
    assert not rpc.broadcasts


def test_live_status_never_loads_keys_or_rpc(tmp_path, capsys, monkeypatch):
    rpc = OfflineRpc()
    invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc)
    capsys.readouterr()
    monkeypatch.setattr(
        lab, "BasePaymentTransport", lambda *a, **k: pytest.fail("status constructed transport")
    )
    assert invoke(tmp_path, "status", rpc=rpc) == 0
    assert "OFFLINE" in capsys.readouterr().out


def test_json_errors_do_not_echo_rpc_secrets(tmp_path, capsys):
    class ExplodingRpc:
        def request(self, *args):
            raise RuntimeError("private-url/secret key=supersecret raw=private-capability")

    code = lab.main(
        ["preflight", "--payment-id", "test", "--journal", str(tmp_path / "new.sqlite3")],
        env={},
        rpc=ExplodingRpc(),
    )
    assert code == 2
    error = capsys.readouterr().err
    assert "eth_chainId" in error
    assert "supersecret" not in error and "private-capability" not in error
    assert json.loads(error)["error"]


def test_reclaim_staging_failure_keeps_original_operation_for_recovery(tmp_path):
    from spikes.payments.reclaim import stage_reclaim
    from test_base_transport import BasePaymentTransport, offline_config

    rpc = OfflineRpc()
    invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc)
    invoke(tmp_path, "fund", "--simulate", rpc=rpc)
    invoke(tmp_path, "reconcile", rpc=rpc)
    journal = PaymentJournal(tmp_path / "lab.sqlite3")
    with journal.transaction() as db:
        payment = journal.payment(db, "capture-a")
        operation = lab.operation_for(payment, "reclaim")
        journal.reserve(db, operation)
    transport = BasePaymentTransport(offline_config(journal.path, signing=True), rpc=rpc)
    with pytest.raises(BaseTransportError, match="accepted payer"):
        stage_reclaim(journal, transport, operation.operation_id, OPERATOR_KEY)
    with journal.transaction() as db:
        assert journal.get(db, operation.operation_id).state == "reserved"
        assert journal.private(db, operation.operation_id)[:2] == (None, None)
    assert len(rpc.broadcasts) == 1


def test_live_mode_dry_run_never_reads_either_signer_even_when_env_enabled(tmp_path):
    from test_base_transport import offline_config

    config = offline_config(tmp_path / "live-fixture.sqlite3")
    rpc = OfflineRpc()

    class PublicOnly(dict):
        def get(self, name, default=None):
            if "PRIVATE_KEY" in name:
                pytest.fail("dry-run accessed signing key")
            return super().get(name, default)

    from eth_account import Account

    env = PublicOnly(
        BASE_OPERATOR_ADDRESS=config.operator_address,
        BASE_PROVIDER_ADDRESS=config.provider_address,
        SPIKE_BUYER_ADDRESS=Account.from_key(BUYER_KEY).address,
        ENABLE_TESTNET_BROADCAST="true",
    )
    common = ["--payment-id", "live-fixture", "--journal", str(config.journal_path)]
    assert lab.main(["prepare", *common, "--save-fixture"], env=env, rpc=rpc) == 0
    for command in lab.COMMANDS:
        assert lab.main([command, *common, "--dry-run"], env=env, rpc=rpc) == 0
    assert not rpc.broadcasts


def test_expired_fixture_does_not_generate_buyer_capability(tmp_path):
    rpc = OfflineRpc()
    assert invoke(tmp_path, "prepare", "--save-fixture", rpc=rpc) == 0
    rpc.timestamp = 1300
    assert invoke(tmp_path, "fund", "--simulate", rpc=rpc) == 2
    _, operations = lab.read_payment(tmp_path / "lab.sqlite3", "capture-a")
    assert operations == ()
    assert not rpc.broadcasts
