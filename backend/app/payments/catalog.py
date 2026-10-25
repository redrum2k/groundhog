"""Catalog policy hooks for the shared payment journal and bounded executor."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contracts.catalog import Binding, Booking, CatalogOrder
from app.contracts.payments import (
    CatalogPaymentIntent,
    FundingPreparation,
    PaymentAccount,
    PaymentBinding,
    PaymentInfo,
    PaymentOperation,
    PaymentTerms,
    PaymentView,
    PaymentWorkResult,
)
from app.orders.dataset import is_dataset
from app.orders.service import DomainError
from app.payments.base_config import (
    BASE_COLLECTOR_ADDRESS,
    BASE_ESCROW_ADDRESS,
    BASE_USDC_ADDRESS,
)
from app.payments.executor import PaymentExecutor
from app.payments.interfaces import PaymentReceipt
from app.payments.journal import PaymentJournal
from app.payments.mock import mock_receipt
from app.payments.protocol import (
    compute_authorization_nonce,
    compute_payment_hash,
    receive_authorization_typed_data,
    usdc_domain,
    validate_payment_terms,
    verify_buyer_signature,
)
from app.runtime.catalog_policy import capture_allowed
from app.runtime.dataset_policy import cutoff

MOCK_DOMAIN = usdc_domain("Mock USDC (no onchain authorization)")
MOCK_PAYER = "0x" + "2" * 40
MOCK_OPERATOR = "0x" + "1" * 40
MOCK_RECEIVER = "0x" + "3" * 40


def fingerprint(command):
    return hashlib.sha256(command.model_dump_json(by_alias=True).encode()).hexdigest()


class CatalogPayments:
    def __init__(self, owner, *, mode="mock", config=None, transport=None, mock_delay_seconds=0):
        if mode not in ("mock", "base_sepolia"):
            raise ValueError("unsupported catalog payment mode")
        if mode == "base_sepolia" and (config is None or owner.auto_mock_funding):
            raise ValueError("Base mode requires explicit configuration and no auto mock funding")
        self.owner, self.mode, self.config, self.transport = owner, mode, config, transport
        if type(mock_delay_seconds) is not int or not 0 <= mock_delay_seconds <= 10:
            raise ValueError("mock payment delay must be an integer between 0 and 10 seconds")
        self.mock_delay_seconds = mock_delay_seconds if mode == "mock" else 0
        self.journal = PaymentJournal(owner.repository)
        self.executor = PaymentExecutor(
            self.journal,
            transport,
            guard=self.guard,
            changed=self.changed,
            complete=self.complete,
            authority=self.attempt_authority,
        )

    @staticmethod
    def is_live(order):
        terms = order.snapshot.quote.payment_terms
        return terms is not None and terms.mode == "base_sepolia"

    def queued_settlement(self, db, order):
        return self.is_live(order) or bool(
            order.payment_id
            and (
                self.mock_delay_seconds
                and is_dataset(order)
                or self.journal.terminal(db, order.payment_id)
            )
        )

    def terms(self, amount, payer, now):
        live = self.mode == "base_sepolia"
        config = self.config
        if live and not payer:
            raise DomainError(422, "Base quote requires an explicit payer")
        if live and (not config.operator_address or not config.provider_address):
            raise DomainError(503, "Base quote requires explicit operator and provider")
        info = PaymentInfo(
            operator=config.operator_address if live else MOCK_OPERATOR,
            payer=payer or MOCK_PAYER,
            receiver=config.provider_address if live else MOCK_RECEIVER,
            token=config.usdc_address if live else BASE_USDC_ADDRESS,
            max_amount=amount.amount_minor * 10000,
            pre_approval_expiry=int((now + timedelta(seconds=180)).timestamp()),
            authorization_expiry=int((now + timedelta(seconds=3600)).timestamp()),
            refund_expiry=int((now + timedelta(seconds=7200)).timestamp()),
            fee_receiver="0x" + "0" * 40,
            salt=secrets.randbits(256),
        )
        return PaymentTerms(
            payment_id="payment-" + uuid4().hex,
            mode=self.mode,
            chain_id=config.chain_id if live else 84532,
            asset_address=info.token,
            amount_atomic=info.max_amount,
            payment_info=info,
            escrow_address=config.escrow_address if live else BASE_ESCROW_ADDRESS,
            collector_address=config.collector_address if live else BASE_COLLECTOR_ADDRESS,
            payment_hash=compute_payment_hash(
                info,
                config.chain_id if live else 84532,
                config.escrow_address if live else BASE_ESCROW_ADDRESS,
            ),
            authorization_nonce=compute_authorization_nonce(
                info,
                config.chain_id if live else 84532,
                config.escrow_address if live else BASE_ESCROW_ADDRESS,
            ),
            confirmations=config.confirmations if live else 2,
            pricing_rule="catalog-usd-usdc-1to1-v1",
            display_amount=amount,
            settlement_terms=(
                "Base Sepolia test USDC escrow; accepted demo conversion 1 USD : 1 USDC; "
                "full capture or full return, zero fees. Funding and settlement require "
                "confirmed payment-specific chain evidence."
            )
            if live
            else (
                "Simulated payment only: accepted demo conversion 1 USD : 1 USDC; "
                "six decimal token units, full capture or full return, zero fees. "
                "No onchain authorization, funding or transfer occurs."
            ),
        )

    def initialize(self, db, order, auto_fund=False, *, parent=None):
        terms = order.snapshot.quote.payment_terms
        if terms is None:
            return
        validate_payment_terms(terms)
        if terms.mode != "mock" and auto_fund:
            raise DomainError(409, "Base funding cannot be simulated")
        blocked = parent is not None and self.is_live(parent)
        now = self.owner.clock()
        payment = PaymentAccount(
            payment_id=terms.payment_id,
            order_id=order.snapshot.order_id,
            snapshot_id=order.snapshot.snapshot_id,
            terms=terms,
            state="blocked_parent" if blocked else "awaiting_signature",
            blocked_by_payment_id=parent.payment_id if blocked else None,
            created_at=now,
            updated_at=now,
        )
        self.journal.create_payment(db, payment)
        if auto_fund and not blocked:
            operation = self._operation(order, "fund", f"{terms.payment_id}:auto-fund")
            self.journal.reserve(db, operation)
            self.journal.complete_mock(db, operation.operation_id)
            self._state(db, payment, "funded")
            order.authorization = order.authorization.model_copy(
                update={
                    "status": "mock_authorized",
                    "receipt": mock_receipt(operation.intent.idempotency_key, "authorize"),
                    "expires_at": datetime.fromtimestamp(info_expiry(terms), UTC),
                }
            )
            order.order_state = "processing"
        else:
            order.authorization = order.authorization.model_copy(
                update={
                    "status": "pending",
                    "receipt": None,
                    "expires_at": datetime.fromtimestamp(info_expiry(terms), UTC),
                }
            )
            order.order_state = "awaiting_authorization"

    def _state(self, db, payment, state, **changes):
        payment = payment.model_copy(
            update={
                "state": state,
                "updated_at": self.owner.clock(),
                **changes,
            }
        )
        self.journal.save_payment(db, payment)
        return payment

    def _operation(self, order, action, key, binding=None):
        terms = order.snapshot.quote.payment_terms
        operation_id = (
            "operation-" + hashlib.sha256(f"{terms.payment_id}:{key}".encode()).hexdigest()[:32]
        )
        intent = CatalogPaymentIntent(
            operation_id=operation_id,
            payment_id=terms.payment_id,
            order_id=order.snapshot.order_id,
            snapshot_id=order.snapshot.snapshot_id,
            binding=PaymentBinding.model_validate((binding or order.binding).model_dump()),
            action=action,
            amount_atomic=terms.amount_atomic,
            payment_hash=terms.payment_hash,
            idempotency_key=key,
            reason="Explicit mock catalog lifecycle decision"
            if terms.mode == "mock"
            else "Accepted catalog lifecycle decision",
            mode=terms.mode,
        )
        return PaymentOperation(
            operation_id=operation_id,
            intent=intent,
            fingerprint=fingerprint(intent),
            created_at=self.owner.clock(),
            updated_at=self.owner.clock(),
        )

    def sync(self, db, order):
        if not order.payment_id:
            return
        payment = self.journal.payment(db, order.payment_id)
        if payment.terms.mode != "mock":
            self._sync_live(db, order, payment)
            return
        terminal = self.journal.terminal(db, payment.payment_id)
        if terminal and terminal.state in ("reserved", "signed"):
            self._sync_live(db, order, payment)
            payment = self.journal.payment(db, payment.payment_id)
        if (
            payment.state in ("awaiting_signature", "funding_pending")
            and order.authorization.receipt is None
            and self.owner.clock().timestamp() >= payment.terms.payment_info.pre_approval_expiry
        ):
            payment = self._state(
                db, payment, "failed", last_error="Funding deadline expired without funding"
            )
        if (
            order.authorization.status == "mock_authorized"
            and payment.state == "awaiting_signature"
        ):
            operation = self._operation(order, "fund", f"{order.payment_id}:auto-fund")
            self.journal.reserve(db, operation)
            self.journal.complete_mock(db, operation.operation_id)
            payment = self._state(db, payment, "funded")
        for booking in order.ledger:
            # Queued mock settlement already committed its journal effect and booking
            # together. Do not import that booking as a second legacy mock operation.
            if terminal and booking.operation_id == terminal.operation_id:
                continue
            action = "capture" if booking.kind == "capture" else "void"
            operation = self._operation(order, action, booking.operation_id, booking.binding)
            self.journal.reserve(db, operation)
            self.journal.complete_mock(db, operation.operation_id)
            desired = "captured" if action == "capture" else "voided"
            if payment.state != desired:
                payment = self._state(db, payment, desired)
        if (
            order.authorization.status == "expired"
            and payment.state
            not in (
                "captured",
                "voided",
                "expired_not_returned",
            )
            and order.authorization.receipt is not None
        ):
            self._state(db, payment, "expired_not_returned")

    def view(self, db, order):
        if not order.payment_id:
            return None
        payment = self.journal.payment(db, order.payment_id)
        return PaymentView(
            payment=payment,
            operations=self.journal.operations(db, payment.payment_id),
            simulated=payment.terms.mode == "mock",
        )

    def _domain(self, terms):
        if terms.mode == "mock":
            return MOCK_DOMAIN
        if self.transport is None:
            raise DomainError(503, "verified Base token domain transport is unavailable")
        try:
            domain = self.transport.verified_usdc_domain()
            if domain.get("name") == MOCK_DOMAIN["name"]:
                raise ValueError("mock domain")
            receive_authorization_typed_data(terms, domain)
            return domain
        except Exception:
            raise DomainError(
                503, "verified Base token domain is unavailable or mismatched"
            ) from None

    def prepare(self, order_id, command):
        request_fingerprint = "prepare:" + fingerprint(command)
        scope = f"funding-preparation:{order_id}"
        with self.owner.repository.transaction() as db:
            replay = self.owner.repository.replay(
                db, scope, command.idempotency_key, request_fingerprint, FundingPreparation
            )
            if replay is not None:
                return replay
            order = self.owner.repository.load(db, "order", order_id, CatalogOrder)
            self.owner._check(order, command)
            if not order.payment_id:
                raise DomainError(409, "historical orders cannot create new payment obligations")
            terms = self.journal.payment_terms(db, order.payment_id)
        domain = self._domain(terms)
        with self.owner.repository.transaction() as db:
            replay = self.owner.repository.replay(
                db, scope, command.idempotency_key, request_fingerprint, FundingPreparation
            )
            if replay is not None:
                return replay
            order = self.owner.repository.load(db, "order", order_id, CatalogOrder)
            self.owner._check(order, command)
            if not order.payment_id:
                raise DomainError(409, "historical orders cannot create new payment obligations")
            payment = self.journal.payment(db, order.payment_id)
            now = self.owner.clock()
            if (
                payment.state != "awaiting_signature"
                or order.order_state != "awaiting_authorization"
                or not self._parent_returned(db, payment)
            ):
                raise DomainError(409, "payment is not awaiting buyer authorization")
            if now.timestamp() >= payment.terms.payment_info.pre_approval_expiry:
                raise DomainError(409, "accepted funding deadline expired")
            preparation = FundingPreparation(
                funding_attempt_id="funding-" + uuid4().hex,
                payment_id=payment.payment_id,
                order_id=order_id,
                binding=PaymentBinding.model_validate(order.binding.model_dump()),
                terms=payment.terms,
                typed_data=receive_authorization_typed_data(payment.terms, domain),
                prepared_at=now,
                expires_at=datetime.fromtimestamp(
                    payment.terms.payment_info.pre_approval_expiry, UTC
                ),
            )
            self.owner.repository.put(
                db, "funding_preparation", preparation.funding_attempt_id, preparation
            )
            self.owner.repository.remember(
                db, scope, command.idempotency_key, request_fingerprint, preparation
            )
            return preparation

    def authorize(self, order_id, command):
        request_fingerprint = "funding-authorization:" + fingerprint(command)
        with self.owner.repository.transaction() as db:
            replay = self.owner.repository.replay(
                db, order_id, command.idempotency_key, request_fingerprint, CatalogOrder
            )
            if replay is not None:
                return replay
            order = self.owner.repository.load(db, "order", order_id, CatalogOrder)
            self.owner._check(order, command)
            if not order.payment_id:
                raise DomainError(409, "historical orders cannot create new payment obligations")
            payment = self.journal.payment(db, order.payment_id)
            preparation = self.owner.repository.load(
                db, "funding_preparation", command.funding_attempt_id, FundingPreparation
            )
            now = self.owner.clock()
            if (
                payment.state != "awaiting_signature"
                or order.order_state != "awaiting_authorization"
                or not self._parent_returned(db, payment)
                or preparation.order_id != order_id
                or preparation.payment_id != payment.payment_id
                or preparation.binding.model_dump() != order.binding.model_dump()
                or preparation.terms != payment.terms
                or command.payment_hash.lower() != payment.terms.payment_hash.lower()
                or now >= preparation.expires_at
            ):
                raise DomainError(
                    409, "funding attempt, binding, payment hash or deadline is stale"
                )
            if command.simulate:
                if payment.terms.mode != "mock":
                    raise DomainError(409, "only mock payments allow simulated authorization")
                signature = None
            else:
                try:
                    verify_buyer_signature(
                        payment.terms,
                        preparation.typed_data.domain.model_dump(),
                        command.signature,
                        int(now.timestamp()),
                    )
                except ValueError as error:
                    raise DomainError(422, str(error)) from None
                signature = command.signature
            operation = self._operation(order, "fund", command.idempotency_key)
            self.journal.reserve(db, operation, private_authorization=signature)
            self._state(db, payment, "funding_pending")
            order.revision += 1
            self.owner._save(db, order)
            self.owner._remember_order(
                db, order_id, command.idempotency_key, request_fingerprint, order
            )
            return order

    def _funded(self, db, payment_id):
        row = db.execute(
            "SELECT operation_id FROM payment_effects WHERE payment_id=? AND kind='fund'",
            (payment_id,),
        ).fetchone()
        return bool(row and self.journal.get(db, row[0]).state == "confirmed")

    def work_allowed(self, db, order):
        if not self.is_live(order):
            return True
        payment = self.journal.payment(db, order.payment_id)
        return (
            payment.state == "funded"
            and self._funded(db, order.payment_id)
            and self._parent_returned(db, payment)
        )

    def reconciling(self, db, order):
        return any(
            o.state in ("submitted", "uncertain", "orphaned")
            for o in self.journal.operations(db, order.payment_id)
        )

    def submitted_capture(self, db, order):
        if not self.is_live(order):
            return False
        operation = self.journal.terminal(db, order.payment_id)
        return bool(
            operation
            and operation.intent.action == "capture"
            and operation.state in ("submitted", "uncertain")
        )

    def _parent_returned(self, db, payment):
        if not payment.blocked_by_payment_id:
            return True
        parent = self.journal.payment(db, payment.blocked_by_payment_id)
        terminal = self.journal.terminal(db, parent.payment_id)
        return bool(
            parent.state == "voided"
            and terminal
            and terminal.intent.action in ("void", "reclaim")
            and terminal.state == "confirmed"
        )

    def _eligible(self, db, order, payment, operation):
        intent = operation.intent
        if (
            order.schema_version != 4
            or order.snapshot.quote.payment_terms != payment.terms
            or intent.binding.model_dump() != order.binding.model_dump()
            or intent.amount_atomic != payment.terms.amount_atomic
            or order.authorization.amount != payment.terms.display_amount
            or order.authorization.expires_at.timestamp() != info_expiry(payment.terms)
        ):
            return False
        now = self.owner.clock()
        if intent.action == "fund":
            return (
                payment.state == "funding_pending"
                and order.order_state == "awaiting_authorization"
                and now.timestamp() < payment.terms.payment_info.pre_approval_expiry
                and self._parent_returned(db, payment)
            )
        terminal = self.journal.terminal(db, payment.payment_id)
        if terminal and terminal.operation_id != operation.operation_id:
            return False
        if (
            order.ledger
            or not self._funded(db, payment.payment_id)
            or not self._parent_returned(db, payment)
        ):
            return False
        if intent.action == "capture":
            return (
                payment.state in ("funded", "capture_pending")
                and capture_allowed(order, now)
                and self.owner.current_dataset_checks(order)
            )
        if intent.action == "void":
            reviewer_authority = any(
                d.action == "release_authorization" and d.binding == order.binding
                for d in order.decisions
            )
            replacement_authority = any(
                child.snapshot.quote.purpose == "substantive_amendment"
                and child.snapshot.quote.parent_order_id == order.snapshot.order_id
                and child.snapshot.quote.parent_binding == order.binding
                for child in (
                    self.owner.repository.load(db, "order", child_id, CatalogOrder)
                    for child_id in order.children
                )
            )
            return payment.state in (
                "funded",
                "void_pending",
                "expired_not_returned",
                "failed",
            ) and (reviewer_authority or replacement_authority)
        return False

    def guard(self, db, operation):
        payment = self.journal.payment(db, operation.intent.payment_id)
        order = self.owner.repository.load(db, "order", payment.order_id, CatalogOrder)
        return self._eligible(db, order, payment, operation)

    def attempt_authority(self, db, operation):
        """Frozen action cutoff; UTC owner clock stays separate from elapsed budget."""
        payment = self.journal.payment(db, operation.intent.payment_id)
        if operation.intent.action == "fund":
            deadline = payment.terms.payment_info.pre_approval_expiry
        elif operation.intent.action == "capture":
            order = self.owner.repository.load(db, "order", payment.order_id, CatalogOrder)
            deadline = cutoff(order).timestamp()
        else:
            return None
        return lambda: deadline - self.owner.clock().timestamp()

    def reserve_terminal(self, db, order, action):
        payment = self.journal.payment(db, order.payment_id)
        existing = self.journal.terminal(db, order.payment_id)
        if existing:
            raise DomainError(409, "payment already has an active or confirmed terminal operation")
        # An invalidated intent retains its exact response/key. A later valid decision
        # gets a new operation without replacing the accepted payment or authorization.
        sequence = len(self.journal.operations(db, order.payment_id))
        operation = self._operation(order, action, f"{order.payment_id}:{action}:{sequence}")
        if not self._eligible(db, order, payment, operation):
            raise DomainError(409, "current payment settlement gates do not pass")
        self.journal.reserve(db, operation)
        self._state(db, payment, "capture_pending" if action == "capture" else "void_pending")

    def _sync_live(self, db, order, payment):
        for operation in self.journal.operations(db, payment.payment_id):
            if operation.state in ("reserved", "signed") and not self._eligible(
                db, order, payment, operation
            ):
                operation = self.journal.invalidate_operation(db, operation.operation_id)
                payment = self._apply_changed(db, order, payment, operation)
        # An elapsed clock cannot settle a submitted operation or prove funds returned.
        if self.reconciling(db, order):
            return
        if (
            payment.state in ("awaiting_signature", "blocked_parent", "funding_pending")
            and self.owner.clock().timestamp() >= payment.terms.payment_info.pre_approval_expiry
        ):
            self._state(db, payment, "failed", last_error="Accepted funding deadline expired")
        elif payment.state == "funded" and order.authorization.status == "expired":
            self._state(db, payment, "expired_not_returned")

    def _apply_changed(self, db, order, payment, operation):
        action, state = operation.intent.action, operation.state
        if state == "confirmed":
            # A repeated canonical observation may clear temporary RPC uncertainty, but
            # never recreate the effect or reopen an order previously put in human review.
            if action == "fund" and self.journal.terminal(db, payment.payment_id):
                return payment
            if action == "fund":
                settlements = [
                    op
                    for op in self.journal.operations(db, payment.payment_id)
                    if op.intent.action != "fund"
                ]
                if settlements and settlements[-1].state == "failed":
                    # Confirming the earlier deposit does not repair a later failed return
                    # or capture. Keep that failure visible until an explicit new operation.
                    return self._state(db, payment, "failed", last_error=settlements[-1].error)
            desired = {"fund": "funded", "capture": "captured", "void": "voided"}[action]
            if action == "fund" and self.owner.clock() >= order.authorization.expires_at:
                desired = "expired_not_returned"
            if order.authorization.status == "uncertain":
                order.authorization = order.authorization.model_copy(
                    update={
                        "status": "released"
                        if action == "void"
                        else (
                            "expired"
                            if self.owner.clock() >= order.authorization.expires_at
                            else "authorized"
                        )
                    }
                )
            if payment.state == desired and payment.last_error is None:
                return payment
            return self._state(
                db, payment, desired, last_error=None, latest_observation=operation.observation
            )
        if state == "invalidated" and action != "fund":
            desired = "funded" if self._funded(db, payment.payment_id) else "uncertain"
            if desired == "funded" and self.owner.clock() >= order.authorization.expires_at:
                desired = "expired_not_returned"
        elif state == "submitted":
            desired = {
                "fund": "funding_pending",
                "capture": "capture_pending",
                "void": "void_pending",
            }[action]
        else:
            desired = {
                "invalidated": "failed",
                "failed": "failed",
                "uncertain": "uncertain",
                "orphaned": "reorg_hold",
            }[state]
        if state in ("uncertain", "orphaned"):
            order.authorization = order.authorization.model_copy(update={"status": "uncertain"})
        if state in ("failed", "orphaned") or state == "invalidated" and action == "fund":
            self.owner._human(order, "Payment requires review: " + (operation.error or state))
        elif state == "uncertain" and action != "fund":
            self.owner._human(
                order, "Settlement outcome is uncertain; reconcile the saved operation."
            )
        return self._state(db, payment, desired, last_error=operation.error)

    def changed(self, db, operation, evidence):
        payment = self.journal.payment(db, operation.intent.payment_id)
        order = self.owner.repository.load(db, "order", payment.order_id, CatalogOrder)
        before = (payment.model_dump_json(), order.model_dump_json())
        payment = self._apply_changed(db, order, payment, operation)
        if before != (payment.model_dump_json(), order.model_dump_json()):
            order.revision += 1
            self.owner.repository.put(db, "order", payment.order_id, order)
            self.owner.effects.state(db, order)

    def complete(self, db, operation, evidence):
        payment = self.journal.payment(db, operation.intent.payment_id)
        order = self.owner.repository.load(db, "order", payment.order_id, CatalogOrder)
        action = operation.intent.action
        now = self.owner.clock()
        receipt_action = {"fund": "authorize", "capture": "capture", "void": "release"}[action]
        receipt = (
            mock_receipt(operation.intent.idempotency_key, receipt_action)
            if operation.intent.mode == "mock"
            else PaymentReceipt(
                idempotency_key=operation.intent.idempotency_key,
                operation_id=operation.operation_id,
                operation=receipt_action,
                mode="live",
                status="confirmed",
                transaction_id=operation.transaction_hash,
            )
        )
        if action == "fund":
            expired = now >= order.authorization.expires_at
            order.authorization = order.authorization.model_copy(
                update={
                    "status": "expired"
                    if expired
                    else ("mock_authorized" if operation.intent.mode == "mock" else "authorized"),
                    "receipt": receipt,
                }
            )
            if expired:
                self.owner._human(order, "Funding confirmed after capture authority expired.")
            elif order.order_state == "awaiting_authorization":
                order.order_state, order.error = "processing", None
            desired = "expired_not_returned" if expired else "funded"
        else:
            if action == "capture" and order.authorization.status == "uncertain":
                order.authorization = order.authorization.model_copy(
                    update={
                        "status": "expired"
                        if now >= order.authorization.expires_at
                        else "authorized"
                    }
                )
            order.ledger = (
                *order.ledger,
                Booking(
                    operation_id=operation.operation_id,
                    kind="capture" if action == "capture" else "release",
                    amount=payment.terms.display_amount,
                    binding=Binding.model_validate(operation.intent.binding.model_dump()),
                    recorded_at=now,
                    receipt=receipt,
                ),
            )
            if action == "void":
                order.authorization = order.authorization.model_copy(update={"status": "released"})
                order.order_state, order.authority_state = "closed", "clear"
            elif (
                operation.intent.binding.model_dump() == order.binding.model_dump()
                and order.authority_state == "clear"
                and not any(
                    c.status in ("open", "human_review", "scope_change") for c in order.cases
                )
            ):
                order.order_state = "closed"
            else:
                self.owner._human(
                    order, "Capture confirmed; late complaint needs human resolution."
                )
            desired = "captured" if action == "capture" else "voided"
        self._state(db, payment, desired, last_error=None, latest_observation=operation.observation)
        order.revision += 1
        self.owner.repository.put(db, "order", payment.order_id, order)
        self.owner.effects.payment(db, order, action, receipt)
        self.owner.effects.state(db, order)
        if action == "void":
            for child_id in order.children:
                child = self.owner.repository.load(db, "order", child_id, CatalogOrder)
                child_payment = self.journal.payment(db, child.payment_id)
                if child_payment.blocked_by_payment_id != payment.payment_id:
                    continue
                expired = now.timestamp() >= child_payment.terms.payment_info.pre_approval_expiry
                self._state(db, child_payment, "failed" if expired else "awaiting_signature")
                if expired:
                    self.owner._human(
                        child, "Parent return confirmed after child funding deadline."
                    )
                child.revision += 1
                self.owner.repository.put(db, "order", child_id, child)
                self.owner.effects.state(db, child)

    def work(self, limit=20):
        if type(limit) is not int or not 0 <= limit <= 20:
            raise ValueError("payment work limit must be between 0 and 20")
        with self.owner.repository.transaction() as db:
            operations = self.journal.pending(db, limit=limit, include_confirmed=True)
        now = self.owner.clock()
        # Keep the real pending state visible in mock demos. The original reservation
        # time survives restarts and retries; no sleep holds a transaction or worker.
        operations = [
            operation
            for operation in operations
            if not (
                operation.intent.mode == "mock"
                and operation.intent.action in ("fund", "capture")
                and operation.state == "reserved"
                and (now - operation.created_at).total_seconds() < self.mock_delay_seconds
            )
        ]
        broadcast = bool(
            getattr(self.transport, "is_fake", False)
            or self.config is not None
            and self.config.enable_testnet_broadcast
        )
        for operation in operations:
            self.executor.run_one(operation.operation_id, broadcast=broadcast)
        return PaymentWorkResult(processed=len(operations), simulated=self.mode == "mock")


def info_expiry(terms):
    return terms.payment_info.authorization_expiry
