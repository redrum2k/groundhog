"""Base Sepolia v1.1 transport. No environment reads, workers, or RPC at import time.

RPC injection: an object with request(method: str, params: list) -> JSON-RPC result.
Signing returns bytes only; the executor persists them before it calls broadcast.
"""

from eth_account import Account
from eth_account.typed_transactions import TypedTransaction
from eth_utils import keccak, to_checksum_address
from hexbytes import HexBytes

from app.contracts.payments import PaymentTerms
from app.payments.attempt import RPC_SECONDS, AttemptStopped, checkpoint, current_attempt
from app.payments.base_rpc import BaseTransportError, HttpRpc, PinnedAbi, hex_bytes, quantity
from app.payments.executor import ChainObservation, SignedTransaction
from app.payments.protocol import (
    PAYMENT_INFO_TYPEHASH,
    payment_info_tuple,
    usdc_domain,
    validate_payment_terms,
    verify_buyer_signature,
    verify_domain_separator,
)

EVENTS = {
    "fund": "PaymentAuthorized",
    "capture": "PaymentCaptured",
    "void": "PaymentVoided",
    "reclaim": "PaymentReclaimed",
}
RECEIVE_TYPEHASH = keccak(
    text=(
        "ReceiveWithAuthorization(address from,address to,uint256 value,"
        "uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    )
)


class BasePaymentTransport:
    def __init__(self, config, *, rpc=None):
        self.config = config
        self.rpc = rpc if rpc is not None else HttpRpc(config.rpc_url)
        self.escrow = PinnedAbi("AuthCaptureEscrow")
        self.collector = PinnedAbi("ERC3009PaymentCollector")
        self.token = PinnedAbi("USDC")

    def _rpc(self, method, params):
        checkpoint(reserve=RPC_SECONDS, effect=method == "eth_sendRawTransaction")
        attempt = current_attempt()
        started = attempt.clock() if attempt else None
        try:
            result = self.rpc.request(method, params)
        except AttemptStopped:
            raise
        except Exception:
            checkpoint()
            raise BaseTransportError(
                f"{method} unavailable; inspect/reconcile before retrying"
            ) from None
        if attempt and method == "eth_getBlockByNumber" and params[0] == "latest" and result:
            attempt.observe_chain(quantity(result["timestamp"]), started)
        checkpoint()
        return result

    def _chain(self):
        if quantity(self._rpc("eth_chainId", [])) != self.config.chain_id:
            raise BaseTransportError("RPC chain differs from Base Sepolia 84532")

    def _block(self, tag="latest"):
        block = self._rpc("eth_getBlockByNumber", [tag, False])
        if not block or len(hex_bytes(block["hash"])) != 32:
            raise BaseTransportError("canonical block unavailable")
        quantity(block["number"])
        quantity(block["timestamp"])
        if tag != "latest" and quantity(block["number"]) != quantity(tag):
            raise BaseTransportError("RPC returned another block number")
        return block

    @staticmethod
    def _at(block):
        # EIP-1898: never silently fall back to latest or an unpinned block number.
        return {"blockHash": block["hash"], "requireCanonical": True}

    def _call(self, abi, address, name, args=(), block="latest"):
        value = self._rpc("eth_call", [{"to": address, "data": abi.encode(name, args)}, block])
        return abi.decode(name, value)

    def _code(self, address, block):
        return hex_bytes(self._rpc("eth_getCode", [address, block]))

    def _domain(self, block):
        if not self._code(self.config.usdc_address, block):
            raise BaseTransportError("configured USDC has no deployed code")
        if self._call(self.token, self.config.usdc_address, "decimals", block=block) != (6,):
            raise BaseTransportError("configured USDC must have six decimals")
        name = self._call(self.token, self.config.usdc_address, "name", block=block)[0]
        domain = usdc_domain(name, chain_id=self.config.chain_id)
        domain["verifyingContract"] = self.config.usdc_address
        separator = self._call(
            self.token, self.config.usdc_address, "DOMAIN_SEPARATOR", block=block
        )[0]
        verify_domain_separator(domain, separator)
        if self._call(
            self.token, self.config.usdc_address, "RECEIVE_WITH_AUTHORIZATION_TYPEHASH", block=block
        ) != (RECEIVE_TYPEHASH,):
            raise BaseTransportError("USDC ReceiveWithAuthorization type is incompatible")
        return domain

    def verified_usdc_domain(self) -> dict:
        """Observe chain, code, decimals, name and separator together; no mock fallback."""
        self._chain()
        block = self._block()
        domain = self._domain(self._at(block))
        self._assert_canonical(block)
        return domain

    def _terms(self, terms):
        # Revalidate even callers using model_copy/model_construct across the boundary.
        terms = PaymentTerms.model_validate(terms.model_dump())
        validate_payment_terms(terms)
        if terms.mode != "base_sepolia":
            raise BaseTransportError("live transport rejects mock payment terms")
        if (
            self.config.provider_address
            and self.config.provider_address.lower() != terms.payment_info.receiver.lower()
        ):
            raise BaseTransportError("configured provider differs from accepted receiver")
        operator = self.config.operator_address
        if operator and operator.lower() != terms.payment_info.operator.lower():
            raise BaseTransportError("configured operator differs from accepted operator")
        return terms

    def _state(self, terms, block):
        return self._call(
            self.escrow,
            self.config.escrow_address,
            "paymentState",
            (hex_bytes(terms.payment_hash),),
            block,
        )

    def _balance(self, address, block):
        return self._call(self.token, self.config.usdc_address, "balanceOf", (address,), block)[0]

    def _assert_canonical(self, block):
        current = self._block(block["number"])
        if current["hash"].lower() != block["hash"].lower():
            raise BaseTransportError("block changed during inspection; recovery required")

    def preflight(self, terms=None, *, action=None):
        """Read-only compatibility and balance checks at one canonical block.

        With action=None report balances/state without requiring unspent funding. With
        an action, require its exact starting state, deadline and minimum gas balance.
        """
        self._chain()
        block = self._block()
        at = self._at(block)
        for address, abi, methods in (
            (
                self.config.escrow_address,
                self.escrow,
                ("authorize", "capture", "void", "reclaim", "getHash", "paymentState"),
            ),
            (self.config.collector_address, self.collector, ("authCaptureEscrow", "collectorType")),
        ):
            code = self._code(address, at)
            if not code or any(abi.selector(name) not in code for name in methods):
                raise BaseTransportError(
                    "pinned deployment code lacks required interface selectors"
                )
        if self._call(
            self.escrow, self.config.escrow_address, "PAYMENT_INFO_TYPEHASH", block=at
        ) != (PAYMENT_INFO_TYPEHASH,):
            raise BaseTransportError("escrow PaymentInfo type is incompatible")
        implementation = self._call(
            self.escrow, self.config.escrow_address, "tokenStoreImplementation", block=at
        )[0]
        if not self._code(implementation, at):
            raise BaseTransportError("token store implementation has no deployed code")
        binding = self._call(
            self.collector, self.config.collector_address, "authCaptureEscrow", block=at
        )[0]
        if binding.lower() != self.config.escrow_address.lower():
            raise BaseTransportError("collector is bound to another escrow")
        if self._call(self.collector, self.config.collector_address, "collectorType", block=at) != (
            0,
        ):
            raise BaseTransportError("collector is not a payment collector")
        domain = self._domain(at)
        report = {
            "chain_id": self.config.chain_id,
            "block_number": quantity(block["number"]),
            "block_hash": block["hash"],
            "timestamp": quantity(block["timestamp"]),
            "domain": domain,
            "compatibility": "pinned addresses/selectors/read probes; no full bytecode attestation",
        }
        if terms is not None:
            terms = self._terms(terms)
            info = terms.payment_info
            if self._call(
                self.escrow, self.config.escrow_address, "getHash", (payment_info_tuple(info),), at
            )[0] != hex_bytes(terms.payment_hash):
                raise BaseTransportError("escrow hash differs from accepted payment hash")
            payer_zeroed = list(payment_info_tuple(info))
            payer_zeroed[1] = "0x" + "00" * 20
            if self._call(
                self.escrow, self.config.escrow_address, "getHash", (tuple(payer_zeroed),), at
            )[0] != hex_bytes(terms.authorization_nonce):
                raise BaseTransportError("escrow hash differs from ERC-3009 nonce")
            for party in (info.operator, info.payer):
                if self._code(party, at):
                    raise BaseTransportError("operator and payer must be dedicated EOAs")
            if info.payer.lower() == info.receiver.lower():
                raise BaseTransportError("laboratory payer and receiver must differ")
            store = self._call(
                self.escrow, self.config.escrow_address, "getTokenStore", (info.operator,), at
            )[0]
            if int(store, 16) == 0:
                raise BaseTransportError("escrow returned zero token store")
            state = self._state(terms, at)
            balances = {
                "buyer": self._balance(info.payer, at),
                "provider": self._balance(info.receiver, at),
                "token_store": self._balance(store, at),
            }
            gas_balances = {
                "operator": quantity(self._rpc("eth_getBalance", [info.operator, at])),
                "payer": quantity(self._rpc("eth_getBalance", [info.payer, at])),
            }
            report.update(
                payment_id=terms.payment_id,
                payment_hash=terms.payment_hash,
                amount_atomic=str(terms.amount_atomic),
                token_store=store,
                payment_state=state,
                balances={k: str(v) for k, v in balances.items()},
                gas_balances={k: str(v) for k, v in gas_balances.items()},
            )
            if action is not None:
                if action not in EVENTS:
                    raise BaseTransportError("unsupported payment action")
                now = report["timestamp"]
                if action == "fund":
                    if state != (False, 0, 0) or balances["buyer"] < terms.amount_atomic:
                        raise BaseTransportError(
                            "fund requires uncollected payment and sufficient buyer USDC"
                        )
                    used = self._call(
                        self.token,
                        self.config.usdc_address,
                        "authorizationState",
                        (info.payer, hex_bytes(terms.authorization_nonce)),
                        at,
                    )[0]
                    if used or not 0 < now < info.pre_approval_expiry:
                        raise BaseTransportError(
                            "buyer authorization is used or outside its funding window"
                        )
                else:
                    if (
                        state != (True, terms.amount_atomic, 0)
                        or balances["token_store"] < terms.amount_atomic
                    ):
                        raise BaseTransportError(
                            "terminal action requires the full uncaptured payment in custody"
                        )
                    if action == "capture" and now >= info.authorization_expiry:
                        raise BaseTransportError(
                            "capture authority expired; funds have not been returned"
                        )
                    if action == "reclaim" and now < info.authorization_expiry:
                        raise BaseTransportError("payer reclaim requires expired capture authority")
                if gas_balances["payer" if action == "reclaim" else "operator"] <= 0:
                    raise BaseTransportError("transaction signer needs Base Sepolia ETH for gas")
        elif action is not None:
            raise BaseTransportError("action preflight requires immutable payment terms")
        self._assert_canonical(block)
        return report

    def pending_nonce(self, operator):
        self._chain()
        return quantity(
            self._rpc("eth_getTransactionCount", [to_checksum_address(operator), "pending"])
        )

    def calldata(self, action, terms, buyer_signature=None):
        """Pure ABI encoding. Funding input must already be a verified raw EOA signature."""
        terms = self._terms(terms)
        info = payment_info_tuple(terms.payment_info)
        if action == "fund":
            raw = (
                hex_bytes(buyer_signature) if isinstance(buyer_signature, str) else buyer_signature
            )
            if not isinstance(raw, bytes) or len(raw) != 65:
                raise BaseTransportError("funding requires a raw 65-byte buyer authorization")
            return self.escrow.encode(
                "authorize", (info, terms.amount_atomic, terms.collector_address, raw)
            )
        if action == "capture":
            return self.escrow.encode(
                "capture", (info, terms.amount_atomic, 0, terms.payment_info.fee_receiver)
            )
        if action in ("void", "reclaim"):
            return self.escrow.encode(action, (info,))
        raise BaseTransportError("unsupported payment action")

    def transaction_request(self, action, terms, nonce, buyer_signature=None):
        """Preflight + simulation + gas estimate, returning an UNSIGNED type-2 transaction.

        reclaim is payer-addressed; callers must reserve the payer nonce durably and
        sign outside the server transport. No nonce allocation or signature occurs here.
        """
        if type(nonce) is not int or nonce < 0:
            raise BaseTransportError("transaction requires an explicitly reserved unsigned nonce")
        report = self.preflight(terms, action=action)
        if action == "fund":
            buyer_signature = verify_buyer_signature(
                terms, report["domain"], buyer_signature, report["timestamp"]
            )
        sender = terms.payment_info.payer if action == "reclaim" else terms.payment_info.operator
        tx = {
            "from": to_checksum_address(sender),
            "to": self.config.escrow_address,
            "value": "0x0",
            "data": self.calldata(action, terms, buyer_signature),
        }
        # Simulate exactly what will be signed. A revert is not a request for a retry.
        self._rpc("eth_call", [tx, "pending"])
        estimate = quantity(self._rpc("eth_estimateGas", [tx, "pending"]))
        gas = (estimate * 120 + 99) // 100
        if not 21000 <= gas <= self.config.max_gas:
            raise BaseTransportError("estimated gas exceeds configured safety bound")
        head = self._block()
        priority = quantity(self._rpc("eth_maxPriorityFeePerGas", []))
        fee = 2 * quantity(head["baseFeePerGas"]) + priority
        if not 0 < fee <= self.config.max_fee_per_gas:
            raise BaseTransportError("estimated gas fee exceeds configured safety bound")
        balance = quantity(self._rpc("eth_getBalance", [sender, "pending"]))
        # Base also charges L1 data/operator fees; reserve a conservative extra margin.
        if balance < gas * fee * 2:
            raise BaseTransportError("signer needs more ETH for gas and L1 fee margin")
        return {
            **tx,
            "chainId": self.config.chain_id,
            "type": 2,
            "nonce": nonce,
            "value": 0,
            "gas": gas,
            "maxPriorityFeePerGas": priority,
            "maxFeePerGas": fee,
        }

    def prepare_transaction(self, action, terms, nonce, buyer_signature=None):
        if action == "reclaim":
            raise BaseTransportError(
                "reclaim needs payer nonce/signing support in the durable executor; "
                "use transaction_request for inspection"
            )
        if not self.config.enable_testnet_broadcast:
            raise BaseTransportError("signing requires ENABLE_TESTNET_BROADCAST=true")
        if not self.config.operator_private_key:
            raise BaseTransportError(
                "set BASE_OPERATOR_PRIVATE_KEY to the dedicated test operator key"
            )
        request = self.transaction_request(action, terms, nonce, buyer_signature)
        checkpoint(effect=True)
        try:
            signed = Account.sign_transaction(request, self.config.operator_private_key)
        except Exception:
            raise BaseTransportError("dedicated operator transaction signing failed") from None
        return SignedTransaction(
            bytes(signed.raw_transaction),
            "0x" + signed.hash.hex(),
            self.config.operator_address,
            nonce,
        )

    def broadcast(self, raw_transaction, explicit_testnet_broadcast=False):
        return self._broadcast(
            raw_transaction,
            explicit_testnet_broadcast,
            self.config.operator_address,
            ("authorize", "capture", "void"),
        )

    def broadcast_reclaim(self, raw_transaction, terms, *, explicit_testnet_broadcast=False):
        """Submit already journaled payer bytes; never loads or uses a buyer key.

        The lab stages payer-signed bytes using PaymentJournal, then routes the existing
        executor's broadcast through this method. Catalog must use its own payer flow.
        """
        terms = self._terms(terms)
        return self._broadcast(
            raw_transaction,
            explicit_testnet_broadcast,
            terms.payment_info.payer,
            ("reclaim",),
            self.calldata("reclaim", terms),
        )

    def _broadcast(self, raw_transaction, explicit, expected_sender, methods, calldata=None):
        if not explicit or not self.config.enable_testnet_broadcast:
            raise BaseTransportError(
                "broadcast requires explicit opt-in and ENABLE_TESTNET_BROADCAST=true"
            )
        self._chain()
        try:
            tx = TypedTransaction.from_bytes(HexBytes(raw_transaction)).as_dict()
            sender = Account.recover_transaction(raw_transaction)
            if (
                tx["type"] != 2
                or tx["chainId"] != self.config.chain_id
                or bytes(tx["to"]) != hex_bytes(self.config.escrow_address)
                or tx["value"] != 0
                or not 21000 <= tx["gas"] <= self.config.max_gas
                or not 0 < tx["maxFeePerGas"] <= self.config.max_fee_per_gas
                or not 0 <= tx["maxPriorityFeePerGas"] <= tx["maxFeePerGas"]
                or not expected_sender
                or sender.lower() != expected_sender.lower()
                or bytes(tx["data"])[:4] not in [self.escrow.selector(name) for name in methods]
                or (calldata is not None and bytes(tx["data"]) != hex_bytes(calldata))
            ):
                raise ValueError
        except Exception:
            raise BaseTransportError(
                "saved transaction is not an allowed escrow transaction for this signer"
            ) from None
        expected = "0x" + keccak(raw_transaction).hex()
        # Read again INSIDE the transport: executor checks precede these slow reads.
        # Decode the saved bytes, including on a later attempt starting at signed.
        method = next(
            name for name in methods if bytes(tx["data"])[:4] == self.escrow.selector(name)
        )
        info = self.escrow.decode(method, "0x" + bytes(tx["data"])[4:].hex(), inputs=True)[0]
        now = quantity(self._block()["timestamp"])
        if (
            (method == "authorize" and now >= info[5])
            or (method == "capture" and now >= info[6])
            or (method == "reclaim" and now < info[6])
        ):
            raise BaseTransportError("saved transaction is outside its accepted action window")
        checkpoint(effect=True)
        observed = self._rpc("eth_sendRawTransaction", ["0x" + raw_transaction.hex()])
        if not isinstance(observed, str) or observed.lower() != expected:
            raise BaseTransportError("broadcast hash mismatch; reconcile saved hash")
        return expected

    def reconcile(self, action, terms, transaction_hash):
        """One bounded observation. Missing, conflicting, or unavailable proof never succeeds."""
        try:
            return self._reconcile(action, self._terms(terms), transaction_hash)
        except AttemptStopped:
            raise
        except Exception:
            return ChainObservation(
                "uncertain",
                error="RPC or payment evidence unavailable/inconsistent; reconcile saved hash",
            )

    def _reconcile(self, action, terms, transaction_hash):
        self._chain()
        if action not in EVENTS or len(hex_bytes(transaction_hash)) != 32:
            raise BaseTransportError("invalid reconciliation intent")
        receipt = self._rpc("eth_getTransactionReceipt", [transaction_hash])
        if receipt is None:
            return ChainObservation(
                "pending", error="receipt absent; missing receipt is not failure"
            )
        if receipt["transactionHash"].lower() != transaction_hash.lower():
            raise BaseTransportError("receipt belongs to another transaction")
        number = quantity(receipt["blockNumber"])
        block_hash = receipt["blockHash"]
        if len(hex_bytes(block_hash)) != 32:
            raise BaseTransportError("receipt block hash malformed")
        block = self._block(receipt["blockNumber"])
        head = self._block()
        confirmations = max(0, quantity(head["number"]) - number + 1)
        evidence = dict(
            block_number=number,
            block_hash=block_hash,
            confirmations=confirmations,
            canonical=block["hash"].lower() == block_hash.lower(),
        )
        if not evidence["canonical"]:
            return ChainObservation(
                "orphaned",
                **evidence,
                error="receipt block is not canonical; manual recovery required",
            )
        tx = self._rpc("eth_getTransactionByHash", [transaction_hash])
        sender = terms.payment_info.payer if action == "reclaim" else terms.payment_info.operator
        if (
            not tx
            or tx["hash"].lower() != transaction_hash.lower()
            or tx["blockHash"].lower() != block_hash.lower()
            or quantity(tx["blockNumber"]) != number
            or tx["from"].lower() != sender.lower()
            or tx["to"].lower() != terms.escrow_address.lower()
            or quantity(tx["value"]) != 0
            or quantity(tx["chainId"]) != terms.chain_id
        ):
            raise BaseTransportError("transaction differs from accepted payment")
        data = tx.get("input", tx.get("data"))
        buyer_signature = None
        if action == "fund":
            decoded = self.escrow.decode("authorize", "0x" + hex_bytes(data)[4:].hex(), inputs=True)
            buyer_signature = decoded[3]
        if data.lower() != self.calldata(action, terms, buyer_signature).lower():
            raise BaseTransportError("transaction calldata differs from accepted payment")
        status = quantity(receipt["status"])
        if status == 0:
            self._assert_canonical(block)
            return ChainObservation(
                "failed" if confirmations >= terms.confirmations else "pending",
                **evidence,
                error="canonical transaction reverted; no transfer success established",
            )
        if status != 1:
            raise BaseTransportError("invalid receipt status")
        matching = []
        for log in receipt["logs"]:
            if log["address"].lower() != terms.escrow_address.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 2 or topics[1].lower() != terms.payment_hash.lower():
                continue
            if (
                log.get("removed", False)
                or log["transactionHash"].lower() != transaction_hash.lower()
                or log["blockHash"].lower() != block_hash.lower()
                or quantity(log["blockNumber"]) != number
            ):
                raise BaseTransportError("event inclusion differs from receipt")
            matching.append(self.escrow.event(EVENTS[action], log))
        if len(matching) != 1:
            raise BaseTransportError("expected exactly one matching payment event")
        event = matching[0]
        if event["amount"] != terms.amount_atomic:
            raise BaseTransportError("event amount differs from accepted full amount")
        if action == "fund" and (
            event["paymentInfo"]
            != tuple(
                v.lower() if isinstance(v, str) else v
                for v in payment_info_tuple(terms.payment_info)
            )
            or event["tokenCollector"].lower() != terms.collector_address.lower()
        ):
            raise BaseTransportError("authorized event differs from immutable payment")
        if action == "capture" and (
            event["feeAmount"] != 0
            or event["feeReceiver"].lower() != terms.payment_info.fee_receiver.lower()
        ):
            raise BaseTransportError("capture fee differs from accepted zero-fee terms")
        expected = (
            True,
            terms.amount_atomic if action == "fund" else 0,
            terms.amount_atomic if action == "capture" else 0,
        )
        if (
            self._state(terms, self._at(block)) != expected
            or self._state(terms, self._at(head)) != expected
        ):
            raise BaseTransportError("payment state conflicts with the operation")
        store = self._call(
            self.escrow,
            terms.escrow_address,
            "getTokenStore",
            (terms.payment_info.operator,),
            self._at(block),
        )[0]
        state = {
            "payment_hash": terms.payment_hash,
            "has_collected_payment": True,
            "capturable_amount": expected[1],
            "refundable_amount": expected[2],
            "block_number": number,
            "block_hash": block_hash,
            "token_store": store,
            "buyer_balance": self._balance(terms.payment_info.payer, self._at(block)),
            "provider_balance": self._balance(terms.payment_info.receiver, self._at(block)),
            "token_store_balance": self._balance(store, self._at(block)),
        }
        if action == "fund" and state["token_store_balance"] < terms.amount_atomic:
            raise BaseTransportError("custody balance conflicts with funding")
        self._assert_canonical(block)
        self._assert_canonical(head)
        return ChainObservation(
            "confirmed" if confirmations >= terms.confirmations else "pending",
            **evidence,
            event={
                "name": EVENTS[action],
                "payment_hash": terms.payment_hash,
                "amount_atomic": terms.amount_atomic,
            },
            payment_state=state,
        )
