"""Thin terminal client of BasePaymentTransport and the shared durable executor."""

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

# Supports the documented uv --directory backend python ../spikes/... invocation.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.contracts.models import Money
from app.contracts.payments import (
    CatalogPaymentIntent,
    PaymentAccount,
    PaymentBinding,
    PaymentInfo,
    PaymentOperation,
    PaymentTerms,
)
from app.orders.service import DomainError
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig
from app.payments.base_rpc import BaseTransportError
from app.payments.executor import PaymentExecutor
from app.payments.journal import PaymentJournal
from app.payments.protocol import (
    compute_authorization_nonce,
    compute_payment_hash,
    receive_authorization_typed_data,
)
from eth_account import Account
from eth_account.messages import encode_typed_data

ACTIONS = ("fund", "capture", "void", "reclaim")
COMMANDS = (
    "preflight",
    "prepare",
    "fund",
    "status",
    "capture",
    "void",
    "reconcile",
    "reclaim",
)


def parser():
    result = argparse.ArgumentParser(
        description="Base Sepolia payment laboratory. Inspection by default; no .env loading.",
        epilog=(
            "Examples: run.py prepare --payment-id capture-a --offline --save-fixture; "
            "run.py status --payment-id capture-a --offline"
        ),
    )
    sub = result.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        p = sub.add_parser(
            command,
            help=f"{command} one durable synthetic payment",
            epilog=f"Examples: run.py {command} --payment-id capture-a --offline --dry-run",
        )
        p.add_argument(
            "--payment-id",
            required=True,
            help="Durable ID; reused forever for these accepted terms",
        )
        p.add_argument(
            "--journal",
            type=Path,
            help="Private SQLite journal (default: PAYMENT_JOURNAL_PATH)",
        )
        p.add_argument(
            "--offline",
            action="store_true",
            help="Use only synthetic keys and an in-process RPC double",
        )
        p.add_argument(
            "--offline-time",
            type=int,
            default=1000,
            help="Synthetic block timestamp; used only with --offline",
        )
        mode = p.add_mutually_exclusive_group()
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Inspect only; never sign, reserve, or submit (default)",
        )
        if command in ACTIONS:
            mode.add_argument(
                "--broadcast-testnet",
                action="store_true",
                help="Requires ENABLE_TESTNET_BROADCAST=true and separate human authorization",
            )
            mode.add_argument(
                "--simulate",
                action="store_true",
                help="Exercise signing/outbox against --offline RPC only",
            )
        if command == "prepare":
            mode.add_argument(
                "--save-fixture",
                action="store_true",
                help="Persist original terms once; never signs or submits",
            )
            p.add_argument("--payer", help="Public buyer EOA; alternatively SPIKE_BUYER_ADDRESS")
            p.add_argument(
                "--authorization-seconds",
                type=int,
                default=3600,
                help="Fixed lifetime for NEW fixtures; never extends existing terms",
            )
    return result


def read_payment(path, payment_id):
    if not path.exists():
        return None, ()
    # Status/dry-run never initialize/migrate a journal or take a write lock.
    with sqlite3.connect("file:" + quote(str(path.resolve())) + "?mode=ro", uri=True) as db:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_accounts'"
        ).fetchone():
            raise BaseTransportError(
                "journal is not a payment laboratory; choose a separate private path"
            )
        try:
            payment = PaymentJournal.payment(db, payment_id)
        except DomainError as error:
            if error.status == 404:
                return None, ()
            raise
        return payment, PaymentJournal.operations(db, payment_id)


def writable_journal(path):
    previous = os.umask(0o077)
    try:
        journal = PaymentJournal(path)
        path.chmod(0o600)
        return journal
    finally:
        os.umask(previous)


def create_fixture(config, payment_id, payer, timestamp, lifetime, *, offline=False):
    if not config.operator_address or not config.provider_address or not payer:
        raise BaseTransportError(
            "prepare needs BASE_OPERATOR_ADDRESS, BASE_PROVIDER_ADDRESS and --payer "
            "(or SPIKE_BUYER_ADDRESS); no key is needed"
        )
    if not 1 <= lifetime <= 3600:
        raise BaseTransportError("--authorization-seconds must be between 1 and 3600")
    info = PaymentInfo(
        operator=config.operator_address,
        payer=payer,
        receiver=config.provider_address,
        token=config.usdc_address,
        max_amount=100000,
        pre_approval_expiry=timestamp + min(300, lifetime),
        authorization_expiry=timestamp + lifetime,
        refund_expiry=timestamp + lifetime + 3600,
        fee_receiver=config.operator_address,
        salt=secrets.randbits(256),
    )
    terms = PaymentTerms(
        payment_id=payment_id,
        mode="base_sepolia",
        asset_address=config.usdc_address,
        amount_atomic=100000,
        payment_info=info,
        escrow_address=config.escrow_address,
        collector_address=config.collector_address,
        payment_hash=compute_payment_hash(info),
        authorization_nonce=compute_authorization_nonce(info),
        pricing_rule="isolated-test-usdc-0.10-v1",
        display_amount=Money(amount_minor=10, currency="USD", decimals=2),
        settlement_terms=("OFFLINE RPC SIMULATION. " if offline else "LABORATORY TESTNET. ")
        + "Independent synthetic 0.10 test-USDC fixture; not a USD 15 catalog order.",
        confirmations=config.confirmations,
    )
    now = datetime.now(UTC)
    return PaymentAccount(
        payment_id=payment_id,
        order_id="lab-order-" + payment_id,
        snapshot_id="lab-snapshot-" + payment_id,
        terms=terms,
        state="awaiting_signature",
        created_at=now,
        updated_at=now,
    )


def operation_for(payment, action):
    identifier = payment.payment_id + ":" + action
    intent = CatalogPaymentIntent(
        operation_id=identifier,
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        snapshot_id=payment.snapshot_id,
        binding=PaymentBinding(
            snapshot_id=payment.snapshot_id, evidence_revision=1, delivery_version=0
        ),
        action=action,
        amount_atomic=100000,
        payment_hash=payment.terms.payment_hash,
        idempotency_key="lab:" + action,
        reason="explicit synthetic laboratory settlement decision",
        mode="base_sepolia",
    )
    now = datetime.now(UTC)
    return PaymentOperation(
        operation_id=identifier,
        intent=intent,
        fingerprint=hashlib.sha256(intent.model_dump_json().encode()).hexdigest(),
        created_at=now,
        updated_at=now,
    )


def laboratory_executor(journal, transport):
    def guard(db, operation):
        payment = journal.payment(db, operation.intent.payment_id)
        if (
            payment.terms.pricing_rule != "isolated-test-usdc-0.10-v1"
            or payment.terms.amount_atomic != 100000
            or not payment.order_id.startswith("lab-order-")
        ):
            raise DomainError(409, "laboratory cannot execute catalog orders")
        if operation.intent.action != "fund" and payment.state != "funded":
            raise DomainError(409, "terminal laboratory decision requires confirmed funding")
        return True

    def complete(db, operation, evidence):
        payment = journal.payment(db, operation.intent.payment_id)
        state = {
            "fund": "funded",
            "capture": "captured",
            "void": "voided",
            "reclaim": "voided",
        }[operation.intent.action]
        journal.save_payment(
            db,
            payment.model_copy(
                update={
                    "state": state,
                    "latest_observation": operation.observation,
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def changed(db, operation, evidence):
        # Hold the laboratory account on uncertainty/reorg. Only confirmed effects
        # move cash state; a failed terminal action does not return held money.
        state = None
        if operation.state == "submitted":
            state = {
                "fund": "funding_pending",
                "capture": "capture_pending",
                "void": "void_pending",
                "reclaim": "void_pending",
            }[operation.intent.action]
        elif operation.state in ("uncertain", "orphaned"):
            state = "reorg_hold" if operation.state == "orphaned" else "uncertain"
        elif operation.state == "failed":
            state = "failed" if operation.intent.action == "fund" else "funded"
        if state:
            payment = journal.payment(db, operation.intent.payment_id)
            journal.save_payment(db, payment.model_copy(update={"state": state}))

    return PaymentExecutor(journal, transport, guard=guard, complete=complete, changed=changed)


def report(payment, operations, *, offline):
    # Explicit allowlist: no raw capabilities, provider URLs, keys, or error payloads.
    return {
        "payment_id": payment.payment_id,
        "evidence": "OFFLINE SYNTHETIC RPC; no real receipt"
        if offline
        else "testnet inspection; confirmation threshold is not L1 finality",
        "state": payment.state,
        "amount_atomic": str(payment.terms.amount_atomic),
        "payment_hash": payment.terms.payment_hash,
        "payment_info": payment.terms.payment_info.model_dump(mode="json"),
        "operations": [
            {
                "action": op.intent.action,
                "state": op.state,
                "nonce": str(op.nonce) if op.nonce is not None else None,
                "transaction_hash": op.transaction_hash if not offline else None,
                "confirmations": op.block_evidence.confirmations if op.block_evidence else 0,
            }
            for op in operations
        ],
    }


def execute(args, *, env=None, rpc=None):
    env = os.environ if env is None else env
    broadcast = getattr(args, "broadcast_testnet", False)
    simulate = getattr(args, "simulate", False)
    if broadcast and (
        args.offline or env.get("ENABLE_TESTNET_BROADCAST", "false").lower() != "true"
    ):
        raise BaseTransportError(
            "--broadcast-testnet requires ENABLE_TESTNET_BROADCAST=true and forbids --offline"
        )
    if simulate and not args.offline:
        raise BaseTransportError("--simulate requires --offline; it cannot contact a live RPC")
    if args.offline:
        from spikes.payments.offline import BUYER_KEY, OfflineRpc, offline_config

        path = args.journal or ROOT / "artifacts/payment-lab.offline.sqlite3"
        config = offline_config(path, signing=simulate)
        rpc = rpc if rpc is not None else OfflineRpc(timestamp=args.offline_time)
    else:
        try:
            config = BasePaymentConfig.from_env(
                env, include_signer=broadcast and args.command != "reclaim"
            )
        except ValueError as error:
            raise BaseTransportError(str(error)) from None
        path = args.journal or Path(config.journal_path)
    payment, operations = read_payment(path, args.payment_id)
    if payment:
        if (
            payment.terms.pricing_rule != "isolated-test-usdc-0.10-v1"
            or not payment.order_id.startswith("lab-order-")
        ):
            raise BaseTransportError("laboratory commands require a separate synthetic fixture")
        if payment.terms.settlement_terms.startswith("OFFLINE RPC") != args.offline:
            raise BaseTransportError(
                "offline fixture cannot become a live obligation; use a separate journal/ID"
            )
    if args.command == "status":
        if not payment:
            raise BaseTransportError(
                "payment not found; run prepare --payment-id ID --save-fixture first"
            )
        return report(payment, operations, offline=args.offline), 0
    if args.offline and payment:
        # Runnable multi-process example: explicitly reconstruct synthetic chain receipts
        # from the private offline journal. This never operates on a live fixture.
        with sqlite3.connect("file:" + quote(str(path.resolve())) + "?mode=ro", uri=True) as db:
            for op in operations:
                raw, _, _ = PaymentJournal.private(db, op.operation_id)
                if raw and op.state in (
                    "submitted",
                    "uncertain",
                    "confirmed",
                    "orphaned",
                ):
                    rpc.mine(raw)
    transport = BasePaymentTransport(config, rpc=rpc)
    if args.command == "preflight":
        result = transport.preflight(payment.terms if payment else None)
        if args.offline:
            result.pop("block_hash", None)
        return {
            "evidence": "offline synthetic RPC" if args.offline else "read-only RPC observation",
            **result,
        }, 0
    if args.command == "prepare":
        if not payment and not args.save_fixture:
            return {
                "payment_id": args.payment_id,
                "dry_run": True,
                "amount_atomic": "100000",
                "next": (
                    "Set public parties, then prepare --payment-id ID --save-fixture "
                    "to freeze terms once. No salt created."
                ),
            }, 0
        if not payment:
            preflight = transport.preflight()
            payer = args.payer or (
                Account.from_key(BUYER_KEY).address
                if args.offline
                else env.get("SPIKE_BUYER_ADDRESS")
            )
            payment = create_fixture(
                config,
                args.payment_id,
                payer,
                preflight["timestamp"],
                args.authorization_seconds,
                offline=args.offline,
            )
            transport.preflight(payment.terms, action="fund")
            journal = writable_journal(path)
            with journal.transaction() as db:
                # Concurrent initializers cannot overwrite the first accepted terms.
                try:
                    payment = journal.payment(db, args.payment_id)
                except DomainError as error:
                    if error.status != 404:
                        raise
                    journal.create_payment(db, payment)
        domain = transport.verified_usdc_domain()
        return {
            **report(payment, operations, offline=args.offline),
            "typed_data": receive_authorization_typed_data(payment.terms, domain),
        }, 0
    if not payment:
        raise BaseTransportError(
            "payment not found; run prepare --payment-id ID --save-fixture first"
        )
    if args.command == "reconcile":
        if args.dry_run:
            return {
                **report(payment, operations, offline=args.offline),
                "dry_run": True,
            }, 0
        candidates = [op for op in operations if op.state not in ("failed", "invalidated")]
        if candidates:
            journal = writable_journal(path)
            laboratory_executor(journal, transport).run_one(candidates[-1].operation_id)
        payment, operations = read_payment(path, args.payment_id)
        code = (
            4
            if operations and operations[-1].state in ("failed", "invalidated")
            else 3
            if operations and operations[-1].state in ("submitted", "uncertain", "orphaned")
            else 0
        )
        return report(payment, operations, offline=args.offline), code
    if not (broadcast or simulate):
        result = transport.preflight(payment.terms)
        return {
            **report(payment, operations, offline=args.offline),
            "dry_run": True,
            "planned_action": args.command,
            "chain_state": result["payment_state"],
            "submission_note": "explicit submission opt-in required",
        }, 0
    journal = writable_journal(path)
    existing = next((op for op in operations if op.intent.action == args.command), None)
    if existing is None:
        signature = None
        if args.command == "fund":
            domain = transport.preflight(payment.terms, action="fund")["domain"]
            key = BUYER_KEY if args.offline else env.get("SPIKE_BUYER_PRIVATE_KEY")
            if not key:
                raise BaseTransportError(
                    "fund requires SPIKE_BUYER_PRIVATE_KEY for this isolated laboratory only"
                )
            try:
                buyer = Account.from_key(key)
                if buyer.address.lower() != payment.terms.payment_info.payer.lower():
                    raise ValueError
                signature = (
                    "0x"
                    + buyer.sign_message(
                        encode_typed_data(
                            full_message=receive_authorization_typed_data(payment.terms, domain)
                        )
                    ).signature.hex()
                )
            except Exception:
                raise BaseTransportError(
                    "laboratory buyer key does not sign the frozen payer terms"
                ) from None
        existing = operation_for(payment, args.command)
        with journal.transaction() as db:
            journal.reserve(db, existing, private_authorization=signature)
    if args.command == "reclaim":
        from spikes.payments.reclaim import ReclaimSubmission, stage_reclaim

        if existing.state == "reserved":
            key = BUYER_KEY if args.offline else env.get("SPIKE_BUYER_PRIVATE_KEY")
            stage_reclaim(journal, transport, existing.operation_id, key)
        transport = ReclaimSubmission(transport, payment.terms)
    result = laboratory_executor(journal, transport).run_one(existing.operation_id, broadcast=True)
    payment, operations = read_payment(path, args.payment_id)
    code = (
        4
        if result.state in ("failed", "invalidated")
        else 3
        if result.state in ("uncertain", "orphaned")
        or (result.state == "submitted" and existing.state != "reserved")
        else 0
    )
    return report(payment, operations, offline=args.offline), code


def main(argv=None, *, env=None, rpc=None):
    args = parser().parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", args.payment_id):
        print(
            json.dumps(
                {"error": "--payment-id needs 1–80 letters, digits, dots, underscores or hyphens"}
            ),
            file=sys.stderr,
        )
        return 2
    try:
        output, code = execute(args, env=env, rpc=rpc)
        print(json.dumps(output, sort_keys=True))
        return code
    except BaseTransportError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    except Exception:
        # Pydantic, SQLite and RPC exceptions can echo inputs/capabilities. Keep
        # diagnostics structural; inspect the private journal locally for recovery.
        print(
            json.dumps(
                {
                    "error": (
                        "configuration, fixture or operation invalid; "
                        "check public parties, journal and frozen terms"
                    )
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
