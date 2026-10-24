"""Invoice v0.2 compatibility for /api/jobflow only; never catalog payment authority."""

import hashlib
import json
import sqlite3
from contextlib import closing, nullcontext
from datetime import timedelta

from app.contracts.api import (
    AcceptQuote,
    CreateOrder,
    LedgerEntry,
    Mutation,
    OpenDispute,
    OrderRecord,
    OrderView,
    ProcessingQuote,
    PublishDelivery,
    QuoteAuthorization,
    QuoteRequest,
    ReportFailure,
    SubmitAnswer,
    SubmitInvestigation,
)
from app.contracts.models import (
    CaseState,
    CustomerAnswer,
    DeliveryState,
    DeliveryVersion,
    EvidenceReference,
    InvestigationInput,
    OrderState,
    PaymentState,
    ProposalBinding,
    SettlementIntent,
)
from app.orders.service import DomainError, utc_now
from app.payments.mock import mock_receipt
from app.runtime.invoice_policy import (
    CaptureContext,
    validate_additional_processing,
    validate_capture,
)
from app.storage.orders import OrderRepository


class OrderService:
    """Local mock workflow. No model, provider, chain or live payment calls."""

    def __init__(self, repository: OrderRepository, clock=utc_now):
        self.repository = repository
        self.clock = clock

    @staticmethod
    def _fingerprint(operation, command) -> str:
        return json.dumps(
            {"operation": operation, "body": command.model_dump(mode="json")}, sort_keys=True
        )

    @staticmethod
    def _replay(db, order_id, key, fingerprint) -> OrderRecord | None:
        row = db.execute(
            "SELECT request, response FROM order_commands WHERE order_id=? AND idempotency_key=?",
            (order_id, key),
        ).fetchone()
        if row:
            if row[0] != fingerprint:
                raise DomainError(409, "idempotency key already used for a different request")
            return OrderRecord.model_validate_json(row[1])
        return None

    def _save_command(self, db, order, command, fingerprint):
        self.repository.save(db, order)
        db.execute(
            "INSERT INTO order_commands VALUES (?, ?, ?, ?)",
            (
                order.snapshot.order_id,
                command.idempotency_key,
                fingerprint,
                order.model_dump_json(),
            ),
        )

    def create(self, command: CreateOrder, *, connection=None) -> OrderRecord:
        order_id = command.snapshot.order_id
        fingerprint = self._fingerprint("create", command)
        with (
            nullcontext(connection) if connection is not None else self.repository.transaction()
        ) as db:
            replay = self._replay(db, order_id, command.idempotency_key, fingerprint)
            if replay:
                return replay
            if self.repository.get(db, order_id):
                raise DomainError(
                    409, "order already exists; accepted snapshots cannot be replaced"
                )
            now = self.clock()
            if command.authorization_expires_at <= now or command.snapshot.accepted_at > now:
                raise DomainError(
                    422, "acceptance must be in the past and authorization must be unexpired"
                )
            if command.snapshot.job_type == "invoice_register" and (
                not command.snapshot.structured_data
                or not any(
                    item.media_type == "application/pdf" for item in command.snapshot.input_versions
                )
            ):
                raise DomainError(
                    422, "invoice orders require source PDF and retained structured data"
                )
            key = f"{order_id}:base:authorize"
            receipt = mock_receipt(key, "authorize")
            order = OrderRecord(
                snapshot=command.snapshot,
                authorization_id=receipt.operation_id,
                authorization_expires_at=command.authorization_expires_at,
                authorization_receipt=receipt,
                evidence=(*command.snapshot.input_versions, *command.snapshot.structured_data),
            )
            self._save_command(db, order, command, fingerprint)
            return order

    def get(self, order_id: str) -> OrderRecord:
        with self.repository.transaction() as db:
            order = self.repository.get(db, order_id)
            if order is None:
                raise DomainError(404, "order not found")
            if self._advance(order, self.clock()):
                order.revision += 1
                self.repository.save(db, order)
            return order

    def mutate(
        self, order_id: str, operation: str, command: Mutation, *, connection=None
    ) -> OrderRecord:
        fingerprint = self._fingerprint(operation, command)
        with (
            nullcontext(connection) if connection is not None else self.repository.transaction()
        ) as db:
            replay = self._replay(db, order_id, command.idempotency_key, fingerprint)
            if replay:
                return replay
            order = self.repository.get(db, order_id)
            if order is None:
                raise DomainError(404, "order not found")
            now = self.clock()
            if self._advance(order, now):
                order.revision += 1
                self.repository.save(db, order)
                # Deadline transitions survive a stale command's rejection.
                if connection is None:
                    db.commit()
                    db.execute("BEGIN IMMEDIATE")
                order = self.repository.get(db, order_id)
            if (
                command.expected_revision != order.revision
                or command.expected_binding != order.binding
            ):
                raise DomainError(
                    409, "stale order revision or evidence binding; refetch the order"
                )
            handler = {
                "delivery": self._publish,
                "failure": self._failure,
                "dispute": self._dispute,
                "answer": self._answer,
                "investigation": self._investigation,
                "accept": self._accept,
                "quote": self._quote,
                "accept_quote": self._accept_quote,
            }[operation]
            handler(order, command, now)
            order.revision += 1
            self._save_command(db, order, command, fingerprint)
            return order

    def expire_due(self) -> int:
        changed = 0
        with self.repository.transaction() as db:
            now = self.clock()
            # Only active invoice jobflow records use this retained policy. Historical
            # invoice snapshots outside jf_orders must stay byte-for-byte read-only.
            rows = db.execute(
                "SELECT o.data FROM orders o JOIN jf_orders j ON j.id=o.order_id"
            ).fetchall()
            for (data,) in rows:
                order = OrderRecord.model_validate_json(data)
                if self._advance(order, now):
                    order.revision += 1
                    self.repository.save(db, order)
                    changed += 1
        return changed

    @staticmethod
    def _hold(order, reason, *, expired=False):
        order.order_state = OrderState.HUMAN_REVIEW
        order.case_state = CaseState.HUMAN_REVIEW
        if order.payment_phase != "booked":
            order.payment_phase = "expired" if expired else "held"
        order.review_deadline = None
        order.failure = reason

    def _advance(self, order, now) -> bool:
        if (
            order.snapshot.policy.policy_version == "broker-review-v0.3"
            and order.payment_phase not in {"booked", "expired"}
            and now >= order.authorization_expires_at
        ):
            self._hold(
                order, "Payment authorization expired independently of human review.", expired=True
            )
            return True
        if order.order_state in (OrderState.CLOSED, OrderState.HUMAN_REVIEW):
            return False
        if order.snapshot.policy.policy_version == "broker-review-v0.3":
            if order.payment_state in {PaymentState.SUBMITTED, PaymentState.UNCERTAIN}:
                self._hold(
                    order, "Existing payment operation requires reconciliation; do not resend."
                )
                return True
            limit = order.snapshot.policy.overall_case_seconds or 1800
            if now >= order.snapshot.accepted_at + timedelta(seconds=limit):
                self._hold(order, "Overall case deadline reached; human review required.")
                return True
        if now >= order.authorization_expires_at and order.payment_phase != "booked":
            self._hold(order, "Payment authorization expired; human review required.", expired=True)
            return True
        if order.review_deadline is None or now < order.review_deadline:
            return False
        if (
            order.case_state == CaseState.OPEN
            or order.regeneration_pending
            or any(
                not item.fulfilled and item.effective_at <= now for item in order.scope_obligations
            )
        ):
            self._hold(order, "Review cutoff reached without resolving the dispute.")
        elif order.order_state == OrderState.DELIVERED:
            from app.data_products import current_data_verification

            if order.snapshot.policy.policy_version == "broker-review-v0.3" and (
                not current_data_verification(order, now)
                or not self._broker_artifacts_valid(order)
                or order.delivery_state != DeliveryState.PASSED
                or order.review_requires_customer_acceptance
            ):
                self._hold(order, "Review cutoff lacks current verification PASS.")
            else:
                self._capture(order, now, "review_cutoff")
        else:
            self._hold(order, "Delivery is unavailable at review cutoff.")
        return True

    @staticmethod
    def _new_binding(order, *, delivery_version=None):
        old = order.binding
        order.binding = ProposalBinding(
            order_id=order.snapshot.order_id,
            snapshot_id=order.snapshot.snapshot_id,
            delivery_version=delivery_version or old.delivery_version,
            evidence_version=old.evidence_version + 1 if old else 1,
            proposal_version=old.proposal_version + 1 if old else 1,
        )
        order.result = None
        order.data_verification = None
        order.quote = None
        order.requires_quote = False

    def _publish(self, order, command: PublishDelivery, now):
        if order.order_state == OrderState.HUMAN_REVIEW:
            raise DomainError(409, "human review must resolve the order before another delivery")
        if (
            order.deliveries
            and not order.regeneration_pending
            and order.order_state != OrderState.FAILED
        ):
            raise DomainError(
                409, "replacement requires an operational failure or supported dispute/defect"
            )
        if not any(item.media_type == "application/pdf" for item in command.artifacts):
            raise DomainError(422, "invoice delivery must include the actual PDF")
        delivery = DeliveryVersion(
            order_id=order.snapshot.order_id,
            snapshot_id=order.snapshot.snapshot_id,
            version=len(order.deliveries) + 1,
            delivered_at=now,
            artifacts=command.artifacts,
            structured_data=command.structured_data,
        )
        order.deliveries = (*order.deliveries, delivery)
        order.evidence = (
            *order.snapshot.input_versions,
            *order.snapshot.structured_data,
            *delivery.artifacts,
            *delivery.structured_data,
        )
        self._new_binding(order, delivery_version=delivery.version)
        order.case_id = f"{order.snapshot.order_id}:delivery:{delivery.version}"
        order.order_state = OrderState.DELIVERED
        order.delivery_state = DeliveryState.PENDING_VERIFICATION
        order.case_state = CaseState.NONE
        order.complaint = None
        order.refund_requested = False
        order.questions = ()
        order.answers = ()
        order.questions_asked = 0
        order.regeneration_pending = False
        order.failure = None
        order.review_deadline = now + timedelta(seconds=order.snapshot.policy.review_window_seconds)
        order.review_requires_customer_acceptance = False
        if order.payment_phase != "booked":
            order.payment_phase = "open"
        self.investigation_input(order)

    def _failure(self, order, command: ReportFailure, now):
        if order.order_state != OrderState.PROCESSING:
            raise DomainError(409, "operational failure requires an active provider job")
        order.failure = f"{command.error_code}: {command.message}"
        order.delivery_state = DeliveryState.OPERATIONAL_FAILURE
        order.order_state = OrderState.FAILED
        order.review_deadline = None
        if order.payment_phase != "booked":
            order.payment_phase = "held"
        if order.regeneration_pending:
            self._hold(order, "The free regeneration failed operationally; human review required.")

    @staticmethod
    def _customer_evidence(order, evidence_id, payload):
        data = json.dumps(payload, sort_keys=True).encode()
        return EvidenceReference(
            evidence_id=evidence_id,
            version=1,
            sha256=hashlib.sha256(data).hexdigest(),
            storage_key=f"db/{evidence_id}",
            media_type="application/json",
            kind="customer_evidence",
        )

    def _dispute(self, order, command: OpenDispute, now):
        if (
            order.order_state not in (OrderState.DELIVERED, OrderState.CLOSED)
            or order.case_state != CaseState.NONE
            or order.review_deadline is None
            or now >= order.review_deadline
        ):
            raise DomainError(
                409, "a new dispute requires an active delivery review without a prior case"
            )
        order.complaint = command.complaint
        order.refund_requested = command.refund_requested
        evidence = self._customer_evidence(
            order,
            f"{order.case_id}:claim",
            {"complaint": command.complaint, "refund_requested": command.refund_requested},
        )
        order.evidence = (*order.evidence, evidence)
        self._new_binding(order)
        order.case_state = CaseState.OPEN
        order.order_state = OrderState.DELIVERED
        order.delivery_state = DeliveryState.NEEDS_REVIEW
        order.review_deadline = now + timedelta(seconds=order.snapshot.policy.review_window_seconds)
        if order.payment_phase != "booked":
            order.payment_phase = "held"

    def _answer(self, order, command: SubmitAnswer, now):
        if order.case_state != CaseState.OPEN:
            raise DomainError(409, "answers require an open investigation")
        if not any(question.question_id == command.question_id for question in order.questions):
            raise DomainError(409, "question is not pending")
        evidence = self._customer_evidence(
            order,
            f"{order.case_id}:answer:{order.questions_asked}",
            {"question_id": command.question_id, "text": command.text},
        )
        order.answers = (
            *order.answers,
            CustomerAnswer(
                question_id=command.question_id,
                text=command.text,
                evidence=evidence,
            ),
        )
        order.evidence = (*order.evidence, evidence)
        order.questions = ()
        self._new_binding(order)

    @staticmethod
    def investigation_input(order: OrderRecord) -> InvestigationInput:
        if not order.deliveries or order.binding is None:
            raise DomainError(409, "investigation requires a delivered PDF")
        return InvestigationInput(
            case_id=order.case_id,
            snapshot=order.snapshot,
            delivery=order.deliveries[-1],
            proposal=order.binding,
            complaint=order.complaint,
            evidence=order.evidence,
            free_regenerations_used=order.free_regenerations_used,
            questions_asked=order.questions_asked,
            answers=order.answers,
        )

    def _investigation(self, order, command: SubmitInvestigation, now):
        if order.snapshot.job_type != "invoice_register":
            raise DomainError(409, "broker verification uses the source-bound data validators")
        if order.order_state not in (OrderState.DELIVERED, OrderState.CLOSED) or order.questions:
            raise DomainError(
                409, "investigation requires an active review with no unanswered question"
            )
        if order.result is not None:
            raise DomainError(409, "this evidence proposal already has a verdict")
        if order.review_deadline is None or now >= order.review_deadline:
            raise DomainError(409, "investigation review has expired")
        result = command.result
        result.validate_for(self.investigation_input(order))
        order.result = result
        if result.verdict == "compliant":
            order.delivery_state = DeliveryState.PASSED
            if order.complaint:
                order.case_state = CaseState.RESOLVED
            if now >= order.authorization_expires_at:
                self._hold(
                    order, "Evidence resolved but payment authorization expired.", expired=True
                )
                return
            self._capture(order, now, "evidence_verdict")
            if result.claim_assessment == "refuted":
                price = order.snapshot.policy.additional_processing_price
                if price:
                    self._additional(order, price, now, "evidence_verdict")
                else:
                    order.requires_quote = True
        elif result.verdict == "provider_defect":
            order.delivery_state = DeliveryState.NEEDS_REVIEW
            self.reserve_free_regeneration(order)
        else:
            order.delivery_state = DeliveryState.NEEDS_REVIEW
            if order.complaint:
                if order.questions_asked == 2 or not result.questions:
                    self._hold(order, "Evidence remains inconclusive; human feedback required.")
                else:
                    used_ids = {answer.question_id for answer in order.answers}
                    if any(question.question_id in used_ids for question in result.questions):
                        raise DomainError(422, "question IDs must be unique within a case")
                    order.questions = result.questions
                    order.questions_asked += len(result.questions)

    def reserve_free_regeneration(self, order):
        if order.free_regenerations_used == 1:
            self._hold(order, "The free regeneration still has a provider defect.")
        else:
            order.free_regenerations_used = 1
            order.regeneration_pending = True
            order.order_state = OrderState.PROCESSING
            order.case_state = CaseState.RESOLVED
            order.review_deadline = None
            if order.payment_phase != "booked":
                order.payment_phase = "held"

    def _capture(self, order, now, reason):
        if order.snapshot.policy.policy_version == "broker-review-v0.3":
            from app.data_products import current_data_verification

            if not current_data_verification(order, now) or not self._broker_artifacts_valid(order):
                raise DomainError(
                    409,
                    "Broker capture requires complete current spec/evidence/delivery verification",
                )
        if any(not item.fulfilled and item.effective_at <= now for item in order.scope_obligations):
            raise DomainError(409, "Effective accepted scope remains unfulfilled")
        if any(entry.kind == "base" for entry in order.ledger):
            order.order_state = OrderState.CLOSED
            return
        intent = SettlementIntent(
            proposal=order.binding,
            action="capture",
            amount=order.snapshot.price,
            authorization_id=order.authorization_id,
            idempotency_key=f"{order.snapshot.order_id}:base:capture",
        )
        result = order.result
        data_result = order.data_verification
        is_broker = order.snapshot.policy.policy_version == "broker-review-v0.3"
        context = CaptureContext(
            current_proposal=order.binding,
            order_state=order.order_state,
            delivery_state=order.delivery_state,
            case_state=order.case_state,
            payment_state=order.payment_state,
            verification_binding=data_result.proposal
            if is_broker and data_result
            else result.proposal
            if result
            else None,
            evidence_verdict=(
                {
                    "PASS": "compliant",
                    "FAIL": "provider_defect",
                    "UNKNOWN": "insufficient_evidence",
                }[data_result.verdict]
                if is_broker and data_result
                else result.verdict
                if result
                else None
            ),
            customer_acceptance=order.binding if reason == "customer_acceptance" else None,
            authorization_id=order.authorization_id,
            authorized_amount=order.snapshot.price,
            authorization_expires_at=order.authorization_expires_at,
            review_deadline=order.review_deadline,
            review_requires_customer_acceptance=order.review_requires_customer_acceptance,
        )
        validate_capture(
            order.snapshot, order.deliveries[-1], intent, context, now=now, simulation=True
        )
        order.ledger = (
            *order.ledger,
            LedgerEntry(
                entry_id=intent.idempotency_key,
                kind="base",
                amount=intent.amount,
                recorded_at=now,
                reason=reason,
                receipt=mock_receipt(intent.idempotency_key, "capture"),
            ),
        )
        order.payment_phase = "booked"
        order.order_state = OrderState.CLOSED

    def _broker_artifacts_valid(self, order):
        """Check stored bytes against frozen references at the financial boundary."""
        try:
            with closing(sqlite3.connect(self.repository.path, timeout=10)) as db:
                for reference in order.evidence:
                    if reference.kind == "customer_evidence":
                        continue
                    row = db.execute(
                        "SELECT metadata,raw FROM jf_artifacts WHERE id=? AND order_id=?",
                        (reference.evidence_id, order.snapshot.order_id),
                    ).fetchone()
                    if row is None:
                        return False
                    metadata = json.loads(row[0])
                    if (
                        metadata["version"] != reference.version
                        or metadata["sha256"] != reference.sha256
                        or hashlib.sha256(bytes(row[1])).hexdigest() != reference.sha256
                    ):
                        return False
            return True
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            return False

    def _accept(self, order, command, now):
        allowed = (
            (CaseState.NONE, CaseState.RESOLVED)
            if order.snapshot.policy.policy_version == "broker-review-v0.3"
            else (CaseState.NONE,)
        )
        if order.order_state != OrderState.DELIVERED or order.case_state not in allowed:
            raise DomainError(409, "acceptance requires an active, undisputed delivery")
        self._capture(order, now, "customer_acceptance")

    def _additional(self, order, amount, now, reason, *, approved_quote=None):
        if now >= order.authorization_expires_at:
            raise DomainError(409, "additional processing authorization has expired")
        key = f"{order.case_id}:additional_processing"
        if any(entry.entry_id == key for entry in order.ledger):
            return
        authority = order.quote_authorization if approved_quote else None
        if approved_quote and (
            authority is None or authority.amount != amount or now >= authority.expires_at
        ):
            raise DomainError(409, "accepted quote requires current payment authorization")
        intent = SettlementIntent(
            proposal=order.binding,
            action="additional_processing",
            amount=amount,
            authorization_id=authority.receipt.operation_id
            if authority
            else order.authorization_id,
            idempotency_key=key,
        )
        validate_additional_processing(
            order.snapshot,
            intent,
            order.result,
            order.binding,
            approved_quote=approved_quote,
        )
        order.ledger = (
            *order.ledger,
            LedgerEntry(
                entry_id=key,
                kind="additional_processing",
                amount=amount,
                recorded_at=now,
                reason=reason,
                receipt=mock_receipt(key, "additional_processing"),
            ),
        )
        order.requires_quote = False

    def _quote(self, order, command: QuoteRequest, now):
        if (
            not order.requires_quote
            or order.result is None
            or order.result.claim_assessment != "refuted"
        ):
            raise DomainError(
                409, "a quote requires a resolved claim without an agreed processing fee"
            )
        if not now < command.expires_at <= order.authorization_expires_at:
            raise DomainError(
                422, "quote expiry must be within the unexpired payment authorization"
            )
        if (command.amount.currency, command.amount.decimals) != (
            order.snapshot.price.currency,
            order.snapshot.price.decimals,
        ):
            raise DomainError(422, "quote must use the accepted currency and precision")
        order.quote = ProcessingQuote(
            quote_id=f"{order.case_id}:quote:{order.revision + 1}",
            amount=command.amount,
            expires_at=command.expires_at,
            binding=order.binding,
        )

    def _accept_quote(self, order, command: AcceptQuote, now):
        quote = order.quote
        if quote is None or quote.quote_id != command.quote_id or quote.binding != order.binding:
            raise DomainError(409, "quote is missing or stale")
        if not order.requires_quote or now >= quote.expires_at:
            raise DomainError(409, "quote is expired or already accepted")
        order.quote_authorization = self.authorize_quote(
            quote.quote_id, quote.amount, "customer_quote_acceptance", quote.expires_at, now
        )
        self._additional(order, quote.amount, now, "accepted_quote", approved_quote=quote.amount)

    @staticmethod
    def authorize_quote(quote_id, amount, actor_id, expires_at, now):
        if now >= expires_at:
            raise DomainError(409, "quote payment authorization must be unexpired")
        return QuoteAuthorization(
            quote_id=quote_id,
            amount=amount,
            authorized_by=actor_id,
            expires_at=expires_at,
            receipt=mock_receipt(f"{quote_id}:authorize", "authorize"),
        )

    def view(self, order: OrderRecord) -> OrderView:
        now = self.clock()
        actions = []
        active = order.review_deadline is not None and now < order.review_deadline
        if active and order.case_state == CaseState.NONE:
            actions.append("dispute")
            if order.order_state == OrderState.DELIVERED:
                actions.append("accept")
        if order.questions and order.case_state == CaseState.OPEN and active:
            actions.append("answer")
        if order.requires_quote and order.quote and now < order.quote.expires_at:
            actions.append("accept_quote")
        if order.delivery_state == DeliveryState.OPERATIONAL_FAILURE:
            display = "operational_failure"
        elif order.order_state == OrderState.HUMAN_REVIEW:
            display = "human_review"
        elif order.delivery_state == DeliveryState.PASSED:
            display = "correct"
        elif order.order_state == OrderState.PROCESSING:
            display = "processing"
        else:
            display = "needs_review"
        return OrderView(
            order=order, server_time=now, available_actions=tuple(actions), display_status=display
        )
