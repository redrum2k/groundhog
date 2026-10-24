"""Catalog payment integration for the explicit offline mock milestone."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contracts.catalog import CatalogOrder
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
from app.orders.service import DomainError
from app.payments.base_config import (
    BASE_COLLECTOR_ADDRESS,
    BASE_ESCROW_ADDRESS,
    BASE_USDC_ADDRESS,
)
from app.payments.journal import PaymentJournal
from app.payments.mock import mock_receipt
from app.payments.protocol import (
    compute_authorization_nonce,
    compute_payment_hash,
    receive_authorization_typed_data,
    usdc_domain,
    verify_buyer_signature,
)

MOCK_DOMAIN = usdc_domain("Mock USDC (no onchain authorization)")
MOCK_PAYER = "0x" + "2" * 40
MOCK_OPERATOR = "0x" + "1" * 40
MOCK_RECEIVER = "0x" + "3" * 40


def fingerprint(command):
    return hashlib.sha256(command.model_dump_json(by_alias=True).encode()).hexdigest()


class CatalogPayments:
    def __init__(self, owner):
        self.owner = owner
        self.journal = PaymentJournal(owner.repository)

    @staticmethod
    def terms(amount, payer, now):
        info = PaymentInfo(
            operator=MOCK_OPERATOR,
            payer=payer or MOCK_PAYER,
            receiver=MOCK_RECEIVER,
            token=BASE_USDC_ADDRESS,
            max_amount=amount.amount_minor * 10000,
            pre_approval_expiry=int((now + timedelta(seconds=180)).timestamp()),
            authorization_expiry=int((now + timedelta(seconds=3600)).timestamp()),
            refund_expiry=int((now + timedelta(seconds=7200)).timestamp()),
            fee_receiver="0x" + "0" * 40,
            salt=secrets.randbits(256),
        )
        return PaymentTerms(
            payment_id="payment-" + uuid4().hex,
            mode="mock",
            asset_address=BASE_USDC_ADDRESS,
            amount_atomic=info.max_amount,
            payment_info=info,
            escrow_address=BASE_ESCROW_ADDRESS,
            collector_address=BASE_COLLECTOR_ADDRESS,
            payment_hash=compute_payment_hash(info),
            authorization_nonce=compute_authorization_nonce(info),
            pricing_rule="catalog-usd-usdc-1to1-v1",
            display_amount=amount,
            settlement_terms=(
                "Simulated payment only: accepted demo conversion 1 USD : 1 USDC; "
                "six decimal token units, full capture or full return, zero fees. "
                "No onchain authorization, funding or transfer occurs."
            ),
        )

    def initialize(self, db, order, auto_fund=False):
        terms = order.snapshot.quote.payment_terms
        if terms is None:
            return
        if terms.mode != "mock":
            raise DomainError(409, "Base execution is not enabled in the offline milestone")
        now = self.owner.clock()
        payment = PaymentAccount(
            payment_id=terms.payment_id,
            order_id=order.snapshot.order_id,
            snapshot_id=order.snapshot.snapshot_id,
            terms=terms,
            state="awaiting_signature",
            created_at=now,
            updated_at=now,
        )
        self.journal.create_payment(db, payment)
        if auto_fund:
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
            reason="Explicit mock catalog lifecycle decision",
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
            return
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
            payment = self.journal.payment(db, order.payment_id)
            now = self.owner.clock()
            if (
                payment.state != "awaiting_signature"
                or order.order_state != "awaiting_authorization"
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
                typed_data=receive_authorization_typed_data(payment.terms, MOCK_DOMAIN),
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
                        payment.terms, MOCK_DOMAIN, command.signature, int(now.timestamp())
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

    def work(self, limit=20):
        processed = 0
        with self.owner.repository.transaction() as db:
            operations = self.journal.pending(db, limit=limit)
            for operation in operations:
                if operation.intent.mode != "mock" or operation.state != "reserved":
                    continue
                payment = self.journal.payment(db, operation.intent.payment_id)
                order = self.owner.repository.load(db, "order", payment.order_id, CatalogOrder)
                if (
                    operation.intent.binding.model_dump() != order.binding.model_dump()
                    or self.owner.clock().timestamp()
                    >= payment.terms.payment_info.pre_approval_expiry
                    or payment.state != "funding_pending"
                ):
                    self.journal.invalidate_operation(db, operation.operation_id)
                    self._state(
                        db, payment, "failed", last_error="Mock funding eligibility expired"
                    )
                    order.order_state, order.error = (
                        "human_review",
                        "Mock funding could not complete.",
                    )
                else:
                    self.journal.complete_mock(db, operation.operation_id)
                    self._state(db, payment, "funded")
                    order.authorization = order.authorization.model_copy(
                        update={
                            "status": "mock_authorized",
                            "receipt": mock_receipt(operation.intent.idempotency_key, "authorize"),
                        }
                    )
                    order.order_state = "processing"
                order.revision += 1
                self.owner._save(db, order)
                processed += 1
        return PaymentWorkResult(processed=processed, simulated=True)


def info_expiry(terms):
    return terms.payment_info.authorization_expiry
