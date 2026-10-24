"""Small synchronous JSON-RPC and pinned ABI boundary; no implicit provider or retries."""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from eth_abi import decode, encode
from eth_utils import keccak

from app.payments.attempt import RPC_SECONDS, AttemptStopped, current_attempt


class BaseTransportError(ValueError):
    """Safe, capability-free message suitable for local diagnostics."""


class HttpRpc:
    def __init__(self, url, *, timeout=RPC_SECONDS):
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
        except ValueError:
            valid = False
        if not valid:
            raise BaseTransportError("set BASE_SEPOLIA_RPC_URL to an HTTP(S) Base Sepolia RPC")
        if not 0 < timeout <= RPC_SECONDS:
            raise ValueError("HTTP elapsed limit must be positive and at most 15 seconds")
        self._url = url
        self.timeout = timeout

    def request(self, method, params):
        """One disposable HTTP-only process, killed/reaped before this call unwinds.

        A socket inactivity timeout cannot bound DNS, TLS or a streaming body. The
        parent instead bounds the entire child lifetime, including startup and drain.
        The child has no signer/journal, inherited environment or retry/redirect loop.
        An interrupted send may already have reached the endpoint: reconcile its ID.
        """
        # BasePaymentTransport fences the claim immediately before entry. Do not
        # acquire another SQLite lock inside the HTTP allowance.
        attempt = current_attempt()
        if attempt is not None:
            attempt.check_time(reserve=self.timeout)
        deadline = time.monotonic() + self.timeout
        # Keep cleanup INSIDE the advertised allowance, not an extra full timeout.
        drain = min(0.25, self.timeout / 4)
        process = None
        try:
            payload = json.dumps([self._url, method, params]).encode()
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", str(Path(__file__).with_name("_http_request.py"))],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={},
                close_fds=True,
            )
            while True:
                if attempt is not None:
                    # No nested journal transaction, renewal or lock while waiting.
                    attempt.check_time()
                remaining = deadline - drain - time.monotonic()
                if remaining <= 0:
                    raise AttemptStopped("HTTP elapsed request limit reached")
                try:
                    output, _ = process.communicate(payload, timeout=min(0.025, remaining))
                    break
                except subprocess.TimeoutExpired:
                    payload = None  # communicate resumes the same request; never retries it.
            if process.returncode:
                raise ValueError
            result = json.loads(output)
            if time.monotonic() >= deadline - drain:
                raise AttemptStopped("HTTP elapsed request limit reached")
            if attempt is not None:
                attempt.check_time()
            return result
        except AttemptStopped as error:
            if attempt is not None:
                attempt.stopped = error
            raise
        except Exception:
            # No URL, method supplied by a remote peer, response, or capability bytes.
            raise BaseTransportError("HTTP RPC unavailable; no automatic retry") from None
        finally:
            if process is not None:
                # Kill the process, not a Python thread. No pipe drain can block on a
                # streaming endpoint after kill; the child never starts descendants.
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=drain)
                finally:
                    process.stdin.close()
                    process.stdout.close()


def hex_bytes(value):
    if not isinstance(value, str) or not value.startswith("0x"):
        raise BaseTransportError("RPC returned malformed hex data")
    try:
        return bytes.fromhex(value[2:])
    except ValueError:
        raise BaseTransportError("RPC returned malformed hex data") from None


def quantity(value):
    if not isinstance(value, str) or not value.startswith("0x"):
        raise BaseTransportError("RPC returned malformed quantity")
    try:
        result = int(value, 16)
        if result < 0:
            raise ValueError
        return result
    except ValueError:
        raise BaseTransportError("RPC returned malformed quantity") from None


def abi_type(item):
    if item["type"] == "tuple":
        return "(" + ",".join(abi_type(part) for part in item["components"]) + ")"
    return item["type"]


def signature(item):
    return item["name"] + "(" + ",".join(abi_type(p) for p in item["inputs"]) + ")"


class PinnedAbi:
    def __init__(self, name):
        entries = json.loads((Path(__file__).parent / "abi" / f"{name}.json").read_text())
        self.entries = {item["name"]: item for item in entries}

    def selector(self, name):
        return keccak(text=signature(self.entries[name]))[:4]

    def encode(self, name, args=()):
        item = self.entries[name]
        return (
            "0x" + (self.selector(name) + encode([abi_type(p) for p in item["inputs"]], args)).hex()
        )

    def decode(self, name, data, *, inputs=False):
        parts = self.entries[name]["inputs" if inputs else "outputs"]
        raw = hex_bytes(data)
        result = decode([abi_type(p) for p in parts], raw)
        if encode([abi_type(p) for p in parts], result) != raw:
            raise BaseTransportError("RPC returned noncanonical ABI data")
        return result

    def event(self, name, log):
        item = self.entries[name]
        topics = log["topics"]
        if len(topics) != 2 or hex_bytes(topics[0]) != keccak(text=signature(item)):
            raise BaseTransportError("receipt event signature differs from pinned ABI")
        payment_hash = hex_bytes(topics[1])
        if len(payment_hash) != 32:
            raise BaseTransportError("receipt event payment hash is malformed")
        parts = [p for p in item["inputs"] if not p["indexed"]]
        raw = hex_bytes(log["data"])
        values = decode([abi_type(p) for p in parts], raw)
        if encode([abi_type(p) for p in parts], values) != raw:
            raise BaseTransportError("receipt event data is noncanonical")
        return {
            "paymentInfoHash": "0x" + payment_hash.hex(),
            **dict(zip((p["name"] for p in parts), values, strict=True)),
        }
