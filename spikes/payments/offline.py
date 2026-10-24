"""Explicit synthetic JSON-RPC laboratory. No provider, socket, or real credentials.

Responses encode Solidity words directly. This is a deterministic RPC double, not an
EVM deployment or a substitute for the separately authorized live acceptance run.
"""

from copy import deepcopy

from app.payments.base_config import (
    BASE_COLLECTOR_ADDRESS,
    BASE_ESCROW_ADDRESS,
    BASE_USDC_ADDRESS,
    BasePaymentConfig,
)
from app.payments.protocol import (
    PAYMENT_INFO_ABI_TYPE,
    PAYMENT_INFO_TYPEHASH,
    usdc_domain,
)
from eth_abi import decode, encode
from eth_account import Account
from eth_account.messages import hash_domain
from eth_account.typed_transactions import TypedTransaction
from eth_utils import keccak
from hexbytes import HexBytes

# Public synthetic scalars, created only by explicit offline setup.
OPERATOR_KEY = "22" * 32
BUYER_KEY = "11" * 32
PROVIDER = "0x5CbDd86a2FA8Dc4bDdd8a8f69dBa48572EeC07FB"
STORE = "0x" + "55" * 20
IMPLEMENTATION = "0x" + "66" * 20
TUPLE = PAYMENT_INFO_ABI_TYPE
FUNCTIONS = {
    "authorize": f"authorize({TUPLE},uint256,address,bytes)",
    "capture": f"capture({TUPLE},uint256,uint256,address)",
    "void": f"void({TUPLE})",
    "reclaim": f"reclaim({TUPLE})",
    "getHash": f"getHash({TUPLE})",
    "paymentState": "paymentState(bytes32)",
    "getTokenStore": "getTokenStore(address)",
    "PAYMENT_INFO_TYPEHASH": "PAYMENT_INFO_TYPEHASH()",
    "tokenStoreImplementation": "tokenStoreImplementation()",
    "authCaptureEscrow": "authCaptureEscrow()",
    "collectorType": "collectorType()",
    "name": "name()",
    "decimals": "decimals()",
    "DOMAIN_SEPARATOR": "DOMAIN_SEPARATOR()",
    "RECEIVE_WITH_AUTHORIZATION_TYPEHASH": "RECEIVE_WITH_AUTHORIZATION_TYPEHASH()",
    "balanceOf": "balanceOf(address)",
    "authorizationState": "authorizationState(address,bytes32)",
}
SELECTORS = {keccak(text=signature)[:4]: name for name, signature in FUNCTIONS.items()}


def encoded(types, values):
    return "0x" + encode(types, values).hex()


def payment_hash(info):
    # Independently spell Solidity's nested abi.encode words.
    words = [PAYMENT_INFO_TYPEHASH]
    for value in info:
        words.append((int(value, 16) if isinstance(value, str) else value).to_bytes(32))
    return (
        "0x"
        + keccak(
            (84532).to_bytes(32)
            + int(BASE_ESCROW_ADDRESS, 16).to_bytes(32)
            + keccak(b"".join(words))
        ).hex()
    )


def offline_config(path, *, signing=False):
    return BasePaymentConfig(
        operator_public_address=Account.from_key(OPERATOR_KEY).address,
        provider_address=PROVIDER,
        operator_private_key=OPERATOR_KEY if signing else None,
        journal_path=str(path),
        enable_testnet_broadcast=signing,
    )


class OfflineRpc:
    is_offline = True

    def __init__(self, *, timestamp=1000):
        self.timestamp = timestamp
        self.height = 101
        self.chain_id = 84532
        self.calls = []
        self.broadcasts = []
        self.receipts = {}
        self.transactions = {}
        self.states = {}
        self.historical_states = {}
        self.balances = {STORE.lower(): 0, PROVIDER.lower(): 0}
        self.historical_balances = {}
        self.nonce = 0
        self.nonces = {}
        self.raise_after_send = False
        self.separator = hash_domain(usdc_domain("USDC"))
        self.collector_escrow = BASE_ESCROW_ADDRESS
        self.decimals = 6
        self.code_missing = None
        self.orphan = False
        self.used = False
        self.gas_balance = 10**18

    def block(self, number):
        block_hash = "0x" + (number + (10000 if self.orphan else 0)).to_bytes(32).hex()
        return {
            "number": hex(number),
            "hash": block_hash,
            "timestamp": hex(self.timestamp),
            "baseFeePerGas": hex(1_000_000),
        }

    def request(self, method, params):
        self.calls.append((method, deepcopy(params)))
        if method == "eth_chainId":
            return hex(self.chain_id)
        if method == "eth_getBlockByNumber":
            return self.block(self.height if params[0] == "latest" else int(params[0], 16))
        if method == "eth_getCode":
            if self.code_missing and params[0].lower() == self.code_missing.lower():
                return "0x"
            if params[0].lower() in [
                x.lower() for x in (BASE_ESCROW_ADDRESS, BASE_COLLECTOR_ADDRESS)
            ]:
                return "0x" + b"".join(b"\x63" + selector for selector in SELECTORS).hex()
            return (
                "0x6000"
                if params[0].lower() in (BASE_USDC_ADDRESS.lower(), IMPLEMENTATION.lower())
                else "0x"
            )
        if method == "eth_getBalance":
            return hex(self.gas_balance)
        if method == "eth_getTransactionCount":
            return hex(self.nonces.get(params[0].lower(), self.nonce))
        if method == "eth_estimateGas":
            return hex(150000)
        if method == "eth_maxPriorityFeePerGas":
            return hex(1000000)
        if method == "eth_call":
            data = bytes.fromhex(params[0]["data"][2:])
            name = SELECTORS[data[:4]]
            args = data[4:]
            if name in ("authorize", "capture", "void", "reclaim"):
                return "0x"
            if name == "getHash":
                return payment_hash(decode([TUPLE], args)[0])
            if name == "paymentState":
                key = "0x" + decode(["bytes32"], args)[0].hex()
                states = self.states
                if isinstance(params[1], dict):
                    states = self.historical_states.get(params[1]["blockHash"], states)
                return encoded(["bool", "uint120", "uint120"], states.get(key, (False, 0, 0)))
            if name == "balanceOf":
                who = decode(["address"], args)[0]
                balances = self.balances
                if isinstance(params[1], dict):
                    balances = self.historical_balances.get(params[1]["blockHash"], balances)
                return encoded(["uint256"], [balances.get(who.lower(), 10**9)])
            values = {
                "name": (["string"], ["USDC"]),
                "decimals": (["uint8"], [self.decimals]),
                "DOMAIN_SEPARATOR": (["bytes32"], [self.separator]),
                "RECEIVE_WITH_AUTHORIZATION_TYPEHASH": (
                    ["bytes32"],
                    [
                        keccak(
                            text=(
                                "ReceiveWithAuthorization(address from,address to,uint256 value,"
                                "uint256 validAfter,uint256 validBefore,bytes32 nonce)"
                            )
                        )
                    ],
                ),
                "PAYMENT_INFO_TYPEHASH": (["bytes32"], [PAYMENT_INFO_TYPEHASH]),
                "getTokenStore": (["address"], [STORE]),
                "tokenStoreImplementation": (["address"], [IMPLEMENTATION]),
                "authCaptureEscrow": (["address"], [self.collector_escrow]),
                "collectorType": (["uint8"], [0]),
                "authorizationState": (["bool"], [self.used]),
            }
            return encoded(*values[name])
        if method == "eth_sendRawTransaction":
            raw = bytes.fromhex(params[0][2:])
            self.broadcasts.append(raw)
            tx_hash = self.mine(raw)
            if self.raise_after_send:
                raise TimeoutError("synthetic lost response")
            return tx_hash
        if method == "eth_getTransactionReceipt":
            return deepcopy(self.receipts.get(params[0]))
        if method == "eth_getTransactionByHash":
            return deepcopy(self.transactions.get(params[0]))
        raise AssertionError(f"unexpected synthetic RPC method {method}")

    def mine(self, raw):
        tx_hash = "0x" + keccak(raw).hex()
        if tx_hash in self.receipts:
            return tx_hash
        tx = TypedTransaction.from_bytes(HexBytes(raw)).as_dict()
        data = bytes(tx["data"])
        name = SELECTORS[data[:4]]
        types = {
            "authorize": [TUPLE, "uint256", "address", "bytes"],
            "capture": [TUPLE, "uint256", "uint256", "address"],
            "void": [TUPLE],
            "reclaim": [TUPLE],
        }[name]
        args = decode(types, data[4:])
        info = args[0]
        phash = payment_hash(info)
        amount = info[4]
        event_name, event_types, event_values = {
            "authorize": (
                "PaymentAuthorized",
                [TUPLE, "uint256", "address"],
                [info, amount, BASE_COLLECTOR_ADDRESS],
            ),
            "capture": (
                "PaymentCaptured",
                ["uint256", "uint256", "address"],
                [amount, 0, info[10]],
            ),
            "void": ("PaymentVoided", ["uint256"], [amount]),
            "reclaim": ("PaymentReclaimed", ["uint256"], [amount]),
        }[name]
        self.height += 2
        block = self.block(self.height - 1)
        self.states[phash] = (
            True,
            amount if name == "authorize" else 0,
            amount if name == "capture" else 0,
        )
        self.historical_states[block["hash"]] = deepcopy(self.states)
        payer, receiver = info[1].lower(), info[2].lower()
        if name == "authorize":
            self.balances[payer] = self.balances.get(payer, 10**9) - amount
            self.balances[STORE.lower()] += amount
        else:
            self.balances[STORE.lower()] -= amount
            recipient = receiver if name == "capture" else payer
            self.balances[recipient] = self.balances.get(recipient, 0) + amount
        self.historical_balances[block["hash"]] = deepcopy(self.balances)
        topic = keccak(text=event_name + "(bytes32," + ",".join(event_types) + ")")
        self.transactions[tx_hash] = {
            "hash": tx_hash,
            "from": Account.recover_transaction(raw),
            "to": BASE_ESCROW_ADDRESS,
            "value": "0x0",
            "chainId": hex(tx["chainId"]),
            "input": "0x" + data.hex(),
            "blockHash": block["hash"],
            "blockNumber": block["number"],
        }
        log = {
            "address": BASE_ESCROW_ADDRESS,
            "topics": ["0x" + topic.hex(), phash],
            "data": encoded(event_types, event_values),
            "blockHash": block["hash"],
            "blockNumber": block["number"],
            "transactionHash": tx_hash,
            "removed": False,
        }
        self.receipts[tx_hash] = {
            "transactionHash": tx_hash,
            "blockHash": block["hash"],
            "blockNumber": block["number"],
            "status": "0x1",
            "logs": [log],
        }
        sender = Account.recover_transaction(raw).lower()
        self.nonces[sender] = max(self.nonces.get(sender, 0), tx["nonce"] + 1)
        return tx_hash
