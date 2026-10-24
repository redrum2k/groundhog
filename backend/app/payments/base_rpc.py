"""Small synchronous JSON-RPC and pinned ABI boundary; no implicit provider or retries."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from eth_abi import decode, encode
from eth_utils import keccak
from web3 import HTTPProvider


class BaseTransportError(ValueError):
    """Safe, capability-free message suitable for local diagnostics."""


class HttpRpc:
    def __init__(self, url):
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
        except ValueError:
            valid = False
        if not valid:
            raise BaseTransportError("set BASE_SEPOLIA_RPC_URL to an HTTP(S) Base Sepolia RPC")
        self._provider = HTTPProvider(
            url, request_kwargs={"timeout": 15}, exception_retry_configuration=None
        )

    def request(self, method, params):
        # Neither provider errors (which may echo a URL/key/raw transaction) nor their
        # exception causes may escape this boundary. Exactly one request, including send.
        try:
            response = self._provider.make_request(method, params)
            if "error" in response or "result" not in response:
                raise ValueError
            return response["result"]
        except Exception:
            raise BaseTransportError(f"{method} unavailable; no automatic retry") from None


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
