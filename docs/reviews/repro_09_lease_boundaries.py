"""Read-only review of 09 code; writes only temporary synthetic test state.

Run with the 09 worktree's backend Python and --worktree pointing at that worktree.
Uses loopback HTTP, never a chain endpoint. Prints no authorization or signed bytes.
"""

import argparse
import contextlib
import io
import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch


def probe_http(base_module, attempt_type, transport_type, rpc_type, offline_config):
    class SlowResponse(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": "0x14a34"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body) + 20))
            self.end_headers()
            try:
                for _ in range(20):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.03)
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = HTTPServer(("127.0.0.1", 0), SlowResponse)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="09-http-review-") as directory:
            rpc = rpc_type(f"http://127.0.0.1:{server.server_port}")
            # Deliberate scaling of the exact 9622fe0 provider configuration.
            # This probe is historical evidence, not a future implementation API.
            rpc._provider._request_kwargs["timeout"] = 0.1
            transport = transport_type(offline_config(Path(directory) / "test.sqlite3"), rpc=rpc)
            started = time.monotonic()
            outcome = "returned"
            with patch.object(base_module, "RPC_SECONDS", 0.1), attempt_type(0.25).scope():
                try:
                    transport._rpc("eth_chainId", [])
                except ValueError as error:
                    outcome = type(error).__name__
            return {
                "finding": "R9-A",
                "rpc_timeout_seconds": 0.1,
                "attempt_budget_seconds": 0.25,
                "actual_elapsed_seconds": round(time.monotonic() - started, 3),
                "result": outcome,
                "network": "loopback synthetic HTTP only",
                "signed_or_broadcast": False,
            }
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def probe_signer(lab, invoke, attempt_type, journal_type, local_account, offline_rpc):
    elapsed = [0.0]
    original_sign = local_account.sign_message

    def late_sign(self, *args, **kwargs):
        signed = original_sign(self, *args, **kwargs)
        elapsed[0] += 301
        return signed

    with tempfile.TemporaryDirectory(prefix="09-sign-review-") as directory:
        path = Path(directory)
        rpc = offline_rpc()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            assert invoke(path, "prepare", "--save-fixture", rpc=rpc) == 0
            with (
                patch.object(lab, "PaymentAttempt", lambda: attempt_type(clock=lambda: elapsed[0])),
                patch.object(local_account, "sign_message", late_sign),
            ):
                code = invoke(path, "fund", "--simulate", rpc=rpc)
        journal = journal_type(path / "lab.sqlite3")
        with journal.transaction() as db:
            operations = journal.operations(db, "capture-a")
            details = [
                {
                    "state": op.state,
                    "has_persisted_buyer_signature": journal.private(db, op.operation_id)[1]
                    is not None,
                    "has_signed_transaction": journal.private(db, op.operation_id)[0] is not None,
                    "nonce": op.nonce,
                }
                for op in operations
            ]
        return {
            "finding": "R9-B",
            "attempt_elapsed_seconds": elapsed[0],
            "attempt_budget_seconds": 300,
            "exit_code": code,
            "operations": details,
            "broadcast_count": len(rpc.broadcasts),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    args = parser.parse_args()
    root = args.worktree.resolve()
    sys.path[:0] = [str(root / "backend"), str(root / "backend/tests/payments"), str(root)]
    from app.payments import base as base_module
    from app.payments.attempt import PaymentAttempt
    from app.payments.base import BasePaymentTransport
    from app.payments.base_rpc import HttpRpc
    from app.payments.journal import PaymentJournal
    from eth_account.signers.local import LocalAccount
    from test_base_transport import lab
    from test_payment_lab import invoke

    from spikes.payments.offline import OfflineRpc, offline_config

    print(
        json.dumps(
            probe_http(base_module, PaymentAttempt, BasePaymentTransport, HttpRpc, offline_config)
        )
    )
    print(
        json.dumps(
            probe_signer(lab, invoke, PaymentAttempt, PaymentJournal, LocalAccount, OfflineRpc)
        )
    )


if __name__ == "__main__":
    main()
