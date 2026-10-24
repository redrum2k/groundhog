"""Durable v0.3 application service. Nikita owns execution; Jeff owns catalog intelligence."""

import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agents.compiler import OfflineCompiler
from app.agents.dataset import compile_dataset
from app.agents.gateway import ClaudeGateway, ModelFailure
from app.catalog.amendments import assess_amendment
from app.catalog.artifacts import ArtifactStore
from app.catalog.documents import extract_source, produce
from app.catalog.preparation import preparation_fingerprint, request_sources
from app.catalog.requirements import specification
from app.catalog.sources import SourceRegistry
from app.catalog.verification import verify
from app.contracts.catalog import (
    Amendment,
    Approval,
    Authorization,
    Binding,
    Booking,
    Case,
    CatalogOrder,
    ClarificationAnswer,
    DatasetDelivery,
    Delivery,
    DisputeContext,
    EvidenceRequest,
    FulfillmentContext,
    Job,
    OrderView,
    Policy,
    PrecontractContext,
    Quote,
    RequestDraft,
    ReviewerDecision,
    Snapshot,
)
from app.contracts.dataset import BrokeragePolicy, DatasetSpecification
from app.contracts.models import Money
from app.datasets import delivery_artifact, is_dataset
from app.investigation.catalog import CatalogInvestigator
from app.orders.dataset import DatasetLifecycle
from app.orders.review import review_table
from app.orders.run_events import CanvasEffects
from app.orders.service import DomainError, utc_now
from app.payments.catalog import CatalogPayments
from app.payments.mock import mock_receipt
from app.runtime.catalog_policy import authorization_ready, capture_allowed
from app.runtime.dataset_policy import cutoff, fits


def identifier(prefix):
    return f"{prefix}-{uuid4().hex}"


class CatalogService(DatasetLifecycle):
    def __init__(
        self,
        repository,
        artifact_root,
        clock=utc_now,
        *,
        compiler=None,
        assessor=None,
        auto_mock_funding=False,
        payment_mode="mock",
        payment_config=None,
        payment_transport=None,
    ):
        self.repository = repository
        self.clock = clock
        self.store = ArtifactStore(artifact_root)
        self.registry = SourceRegistry(repository, self.store)
        self.compiler = compiler or OfflineCompiler()
        # Claude has a distinct structured aggregate-intent path. Offline catalog
        # prompts must never replace the deterministic aggregate consent gates.
        self.dataset_compiler = None if isinstance(compiler, OfflineCompiler) else compiler
        self.investigator = CatalogInvestigator(assessor)
        self.policy = Policy()
        self.auto_mock_funding = auto_mock_funding
        self.effects = CanvasEffects(self)
        self.payments = CatalogPayments(
            self, mode=payment_mode, config=payment_config, transport=payment_transport
        )

    def _save(self, db, order):
        if order.schema_version < 4:
            raise DomainError(409, "historical catalog orders are read-only")
        self.payments.sync(db, order)
        self.repository.put(db, "order", order.snapshot.order_id, order)
        self.effects.state(db, order)

    @staticmethod
    def _response_key(scope, key):
        return hashlib.sha256(json.dumps([scope, key]).encode()).hexdigest()

    def _remember_order(self, db, scope, key, fingerprint, order):
        self.repository.remember(db, scope, key, fingerprint, order)
        self.repository.put(
            db, "order_response", self._response_key(scope, key), self.view(order, db=db)
        )

    def command_view(self, order, key, *, scope=None):
        response_key = self._response_key(scope or order.snapshot.order_id, key)
        with self.repository.transaction() as db:
            row = db.execute(
                "SELECT data FROM catalog_records WHERE kind='order_response' AND id=?",
                (response_key,),
            ).fetchone()
        return OrderView.model_validate_json(row[0]) if row else self.view(order)

    def create_request(self, command):
        fingerprint = self.repository.fingerprint("request", command)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, "requests", command.idempotency_key, fingerprint, RequestDraft
            )
            if replay:
                return replay
            self.registry.manifest(command.corpus_id, db)
            now = self.clock()
            draft = RequestDraft(
                request_id=identifier("request"),
                prompt=command.prompt,
                corpus_id=command.corpus_id,
                created_at=now,
                deadline=now + timedelta(seconds=self.policy.clarification_seconds),
            )
            self.repository.put(db, "request", draft.request_id, draft)
            if draft.corpus_id.endswith("aggregate-v1"):
                self.effects.created(db, draft)
            self.repository.remember(db, "requests", command.idempotency_key, fingerprint, draft)
            return draft

    def get_request(self, request_id):
        with self.repository.transaction() as db:
            draft = self.repository.load(db, "request", request_id, RequestDraft)
            if self.clock() >= draft.deadline and draft.status not in ("accepted", "human_review"):
                draft.status, draft.error = "human_review", "Pre-contract clarification expired."
                draft.revision += 1
                self.repository.put(db, "request", request_id, draft)
                if draft.corpus_id.endswith("aggregate-v1"):
                    self.effects.compiled(db, draft)
            return draft

    def compile_request(self, request_id, command, *, prepared_sources=None):
        fingerprint = (
            preparation_fingerprint(prepared_sources.encounter_id)
            if prepared_sources is not None
            else self.repository.fingerprint("compile", command)
        )
        scope = f"request:{request_id}"
        self.get_request(request_id)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, scope, command.idempotency_key, fingerprint, RequestDraft
            )
            if replay:
                return replay
            draft = self.repository.load(db, "request", request_id, RequestDraft)
            if draft.revision != command.expected_revision or draft.status != "compiling":
                raise DomainError(409, "draft revision/state is stale")
            if draft.compiler_calls >= 4:
                draft.status, draft.error = "human_review", "Compiler call budget exhausted."
                draft.revision += 1
                self.repository.put(db, "request", request_id, draft)
                if draft.corpus_id.endswith("aggregate-v1"):
                    self.effects.compiled(db, draft)
                self.repository.remember(db, scope, command.idempotency_key, fingerprint, draft)
                return draft
            sources = self.registry.manifest(draft.corpus_id, db)
            if prepared_sources is not None:
                prepared_sources.validate_current(sources, self.clock())
                self.repository.put(db, "prepared_sources", request_id, prepared_sources)
                sources = prepared_sources.sources
            else:
                # Ordinary recompilation must not retain an old prepared selection.
                db.execute(
                    "DELETE FROM catalog_records WHERE kind='prepared_sources' AND id=?",
                    (request_id,),
                )
            draft.compiler_calls += 1
            draft.revision += 1
            reserved_revision = draft.revision
            self.repository.put(db, "request", request_id, draft)
            self.repository.remember(db, scope, command.idempotency_key, fingerprint, draft)
        # No database lock during model calls; only allowlisted request and registry evidence.
        try:
            dataset = draft.corpus_id.endswith("aggregate-v1")
            if dataset:
                context = PrecontractContext(draft=draft, sources=sources)
                if isinstance(self.dataset_compiler, ClaudeGateway):
                    proposal = self.dataset_compiler.interpret_dataset(context)
                    with self.repository.transaction() as db:
                        self.repository.put(
                            db, "dataset_intake", f"{request_id}:{reserved_revision}", proposal
                        )
                    result = compile_dataset(context, self.store, proposal=proposal)
                else:
                    result = (
                        self.dataset_compiler.compile(context)
                        if self.dataset_compiler
                        else compile_dataset(context, self.store)
                    )
                if result.terms and not isinstance(result.terms, DatasetSpecification):
                    raise ValueError("aggregate intake requires a versioned dataset specification")
            else:
                observations = []
                for source in sources:
                    extracted = extract_source(source, self.store)
                    observations.extend(extracted.parse_errors)
                    missing = [
                        p.product_id
                        for p in extracted.products
                        if p.net_kg is None or p.unit_price is None
                    ]
                    if missing:
                        observations.append(
                            f"{source.source_id}: unreadable required values for "
                            f"{', '.join(missing)}; "
                            "evidence repair may block fulfillment."
                        )
                    if source.authority == "unverified":
                        observations.append(
                            f"{source.source_id}: supplier authority is unverified."
                        )
                result = self.compiler.compile(
                    PrecontractContext(
                        draft=draft, sources=sources, source_observations=tuple(observations)
                    )
                )
                result = result.model_copy(
                    update={
                        "limitations": tuple(dict.fromkeys((*result.limitations, *observations)))
                    }
                )
            failure = None
        except (ModelFailure, ValueError) as exc:
            result, failure = None, str(exc)
        with self.repository.transaction() as db:
            current = self.repository.load(db, "request", request_id, RequestDraft)
            if (
                current.revision != reserved_revision
                or current.status != "compiling"
                or self.clock() >= current.deadline
            ):
                raise DomainError(409, "stale compiler result; refetch draft")
            if failure:
                current.status, current.error = "human_review", failure
            elif result.question:
                if current.questions_asked >= (
                    2
                    if current.corpus_id.endswith("aggregate-v1")
                    else self.policy.clarification_rounds
                ):
                    current.status, current.error = (
                        "human_review",
                        "Clarification budget exhausted.",
                    )
                else:
                    current.question = result.question
                    current.question_history = (*current.question_history, result.question)
                    current.questions_asked += 1
                    current.status = "clarification"
            else:
                if result.terms.corpus_id != current.corpus_id:
                    raise ValueError("compiler changed selected corpus")
                current.specification = specification(
                    result.terms, current.revision, result.summary, result.limitations
                )
                current.question, current.status = None, "ready"
            current.revision += 1
            self.repository.put(db, "request", request_id, current)
            if current.corpus_id.endswith("aggregate-v1"):
                self.effects.compiled(db, current)
            db.execute(
                "UPDATE catalog_commands SET response=? WHERE scope=? AND key=?",
                (current.model_dump_json(), scope, command.idempotency_key),
            )
            return current

    def clarify(self, request_id, command):
        self.get_request(request_id)
        fingerprint = self.repository.fingerprint("clarify", command)
        with self.repository.transaction() as db:
            scope = f"request:{request_id}"
            replay = self.repository.replay(
                db, scope, command.idempotency_key, fingerprint, RequestDraft
            )
            if replay:
                return replay
            draft = self.repository.load(db, "request", request_id, RequestDraft)
            if (
                draft.revision != command.expected_revision
                or draft.status != "clarification"
                or not draft.question
                or draft.question.question_id != command.question_id
            ):
                raise DomainError(409, "clarification is stale or not pending")
            draft.answers = (
                *draft.answers,
                ClarificationAnswer(question_id=command.question_id, text=command.text),
            )
            if draft.corpus_id.endswith("aggregate-v1"):
                self.effects.message(
                    db,
                    request_id,
                    f"answer:{draft.question.question_id}",
                    command.text,
                    speaker="buyer",
                )
            draft.question, draft.status = None, "compiling"
            draft.revision += 1
            self.repository.put(db, "request", request_id, draft)
            self.repository.remember(db, scope, command.idempotency_key, fingerprint, draft)
            return draft

    @staticmethod
    def price(purpose):
        return Money(amount_minor=1500 if purpose == "initial" else 500, currency="USD", decimals=2)

    def issue_quote(self, request_id, command):
        self.get_request(request_id)
        fingerprint = self.repository.fingerprint("quote", command)
        with self.repository.transaction() as db:
            scope = f"request:{request_id}"
            replay = self.repository.replay(db, scope, command.idempotency_key, fingerprint, Quote)
            if replay:
                return replay
            draft = self.repository.load(db, "request", request_id, RequestDraft)
            if draft.revision != command.expected_revision or draft.status != "ready":
                raise DomainError(409, "quote requires current completed specification")
            dataset = isinstance(draft.specification.terms, DatasetSpecification)
            if dataset and any(
                q.request_id == request_id and q.purpose != "initial"
                for q in self.repository.all(db, "quote", Quote)
            ):
                raise DomainError(409, "Child offer price and purpose are fixed; accept that offer")
            price = (
                Money(amount_minor=12000, currency="USD", decimals=2)
                if dataset
                else self.price("initial")
            )
            quote = Quote(
                quote_id=identifier("quote"),
                request_id=request_id,
                request_revision=draft.revision,
                specification=draft.specification,
                sources=request_sources(self, draft, db),
                amount=price,
                policy=BrokeragePolicy() if dataset else self.policy,
                payment_terms=self.payments.terms(
                    price, getattr(command, "payer", None), self.clock()
                ),
                expires_at=min(draft.deadline, self.clock() + timedelta(seconds=180)),
                work_description=(
                    "Produce and independently verify synthetic aggregate CSV and JSON preview."
                    if dataset
                    else "Produce and verify a complete cited supplier-catalog PDF shortlist."
                ),
            )
            self.repository.put(db, "quote", quote.quote_id, quote)
            if dataset:
                self.effects.quoted(db, quote)
            self.repository.remember(db, scope, command.idempotency_key, fingerprint, quote)
            return quote

    def accept_quote(self, command):
        fingerprint = self.repository.fingerprint("accept_quote", command)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, "acceptance", command.idempotency_key, fingerprint, CatalogOrder
            )
            if replay:
                return replay
            quote = self.repository.load(db, "quote", command.quote_id, Quote)
            now = self.clock()
            if now >= quote.expires_at:
                raise DomainError(409, "quote expired")
            if quote.payment_terms is None:
                raise DomainError(409, "historical quote requires a new payment quote")
            if now.timestamp() >= quote.payment_terms.payment_info.pre_approval_expiry:
                raise DomainError(409, "quote funding window expired; request a new quote")
            order_id = f"order-{quote.quote_id}"
            if db.execute(
                "SELECT 1 FROM catalog_records WHERE kind='order' AND id=?", (order_id,)
            ).fetchone():
                raise DomainError(409, "quote already accepted")
            parent = None
            if quote.purpose == "initial":
                draft = self.repository.load(db, "request", quote.request_id, RequestDraft)
                if (
                    draft.revision != quote.request_revision
                    or draft.status != "ready"
                    or now >= draft.deadline
                ):
                    raise DomainError(409, "quote specification is stale")
                if quote.sources != request_sources(self, draft, db):
                    raise DomainError(409, "source registry changed; obtain a new quote")
                draft.status, draft.order_id = "accepted", order_id
                draft.revision += 1
                self.repository.put(db, "request", draft.request_id, draft)
            else:
                parent = self.repository.load(db, "order", quote.parent_order_id, CatalogOrder)
                if parent.binding != quote.parent_binding or now >= parent.authorization.expires_at:
                    raise DomainError(
                        409, "additional-work quote has a stale parent binding/authority"
                    )
                if (
                    quote.purpose == "substantive_amendment"
                    and parent.authority_state != "pending_consent"
                ):
                    raise DomainError(409, "amendment is no longer pending consent")
            for source in quote.sources:
                self.store.read(source.artifact)
            snapshot = Snapshot(
                schema_version=4,
                snapshot_id=identifier("snapshot"),
                order_id=order_id,
                quote=quote,
                accepted_at=now,
                customer_actor=command.customer_actor,
            )
            binding = Binding(
                snapshot_id=snapshot.snapshot_id, evidence_revision=1, delivery_version=0
            )
            key = f"{order_id}:authorize"
            authorization = Authorization(
                authorization_id=key,
                amount=quote.amount,
                expires_at=datetime.fromtimestamp(
                    quote.payment_terms.payment_info.authorization_expiry, UTC
                ),
                status="mock_authorized" if self.auto_mock_funding else "pending",
                receipt=mock_receipt(key, "authorize") if self.auto_mock_funding else None,
            )
            order = CatalogOrder(
                schema_version=4,
                payment_id=quote.payment_terms.payment_id,
                order_state="processing" if self.auto_mock_funding else "awaiting_authorization",
                snapshot=snapshot,
                binding=binding,
                authorization=authorization,
                sources=quote.sources,
                artifacts=tuple(s.artifact for s in quote.sources),
                jobs=(Job(job_id=f"{order_id}:initial", kind="fulfill", binding=binding),),
            )
            replacement = parent is not None and quote.purpose == "substantive_amendment"
            self.payments.initialize(
                db, order, self.auto_mock_funding, parent=parent if replacement else None
            )
            if is_dataset(order):
                if quote.purpose != "initial":
                    draft = self.repository.load(db, "request", quote.request_id, RequestDraft)
                    draft.status, draft.order_id = "accepted", order_id
                    draft.revision += 1
                    self.repository.put(db, "request", draft.request_id, draft)
                if self.auto_mock_funding:
                    raise DomainError(409, "brokerage requires explicit funding authorization")
                self.effects.accepted(db, order)
            # Funding gates execution; accepting terms only reserves the durable job.
            self._save(db, order)
            if parent:
                parent.children = (*parent.children, order_id)
                if quote.purpose == "substantive_amendment":
                    self._release(parent, now, db=db)
                    if not self.payments.is_live(parent):
                        parent.order_state, parent.authority_state = "closed", "clear"
                parent.revision += 1
                self._save(db, parent)
            self._remember_order(db, "acceptance", command.idempotency_key, fingerprint, order)
            return order

    def get(self, order_id, *, db=None):
        if db is None:
            with self.repository.transaction() as read_db:
                return self.get(order_id, db=read_db)
        order = self.repository.load(db, "order", order_id, CatalogOrder)
        if self._advance(order, self.clock(), db=db):
            order.revision += 1
            self._save(db, order)
        return order

    def current_view(self, order_id):
        # Order revision, actions and payment observations form one consistent read.
        with self.repository.transaction() as db:
            return self.view(self.get(order_id, db=db), db=db)

    def _check(self, order, command):
        if order.schema_version < 4:
            raise DomainError(409, "historical catalog orders are read-only")
        if command.expected_revision != order.revision or (
            command.expected_binding.model_dump() != order.binding.model_dump()
        ):
            raise DomainError(409, "stale revision or evidence binding; refetch")

    def mutate(self, order_id, operation, command, *, actor=None, advance=True):
        if advance:
            with self.repository.transaction() as db:
                current = self.repository.load(db, "order", order_id, CatalogOrder)
            if not is_dataset(current):
                self.get(order_id)
        fingerprint = self.repository.fingerprint(
            operation if actor is None else f"{operation}:{actor}", command
        )
        if operation == "dispute" and command.complaint.column is None:
            historical = json.loads(fingerprint)
            historical["payload"]["complaint"].pop("column")
            fingerprint = json.dumps(historical, sort_keys=True)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, order_id, command.idempotency_key, fingerprint, CatalogOrder
            )
            if replay:
                return replay
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check(order, command)
            handler = {
                "accept": self._accept,
                "dispute": self._dispute,
                "answer": self._answer,
                "approval_customer": self._approve_customer,
                "approval_provider": self._approve_provider,
                "review": self._review,
                "retry": self._retry,
            }[operation]
            if operation in ("accept", "review", "dispute"):
                handler(order, command, self.clock(), actor, db=db)
            else:
                handler(order, command, self.clock(), actor)
            order.revision += 1
            self._save(db, order)
            self._remember_order(db, order_id, command.idempotency_key, fingerprint, order)
            return order

    @staticmethod
    def _human(order, reason):
        order.order_state = "human_review"
        order.error = reason
        order.cases = tuple(
            c.model_copy(update={"status": "human_review"}) if c.status == "open" else c
            for c in order.cases
        )

    def _advance(self, order, now, *, db=None):
        if order.schema_version < 4 or order.order_state == "closed":
            return False
        terms = order.snapshot.quote.payment_terms
        if self.payments.is_live(order) and self.payments.reconciling(db, order):
            return False
        if (
            terms
            and order.authorization.status == "pending"
            and order.order_state == "awaiting_authorization"
            and now.timestamp() >= terms.payment_info.pre_approval_expiry
        ):
            self._human(order, "Funding deadline expired; a new quote is required.")
            return True
        if now >= order.authorization.expires_at and order.authorization.status not in (
            "expired",
            "released",
        ):
            order.authorization = order.authorization.model_copy(update={"status": "expired"})
            self._human(order, "Authorization expired; no reviewer can override expiry.")
            return True
        if is_dataset(order) and now >= cutoff(order) and order.authorization.status != "released":
            if (
                order.order_state == "human_review"
                and order.error
                == "Capture scheduling budget exhausted; release/reclaim requires confirmed return."
            ):
                return False
            self._human(
                order,
                "Capture scheduling budget exhausted; release/reclaim requires confirmed return.",
            )
            return True
        if (
            is_dataset(order)
            and order.order_state == "processing"
            and not fits(order, now, "publication")
        ):
            self._human(order, "Processing cannot finish within the full accepted review budget.")
            return True
        if order.order_state == "human_review":
            return False
        if any(c.status == "open" and now >= c.deadline for c in order.cases):
            self._human(order, "Dispute investigation deadline expired with unresolved facts.")
            return True
        if (
            order.repair_deadline
            and now >= order.repair_deadline
            and order.order_state in ("waiting_evidence", "pending_approval", "processing")
        ):
            self._human(order, "Evidence repair or approval deadline expired.")
            return True
        if self.payments.is_live(order) and self.payments.journal.terminal(db, order.payment_id):
            return False
        if order.deliveries and now >= order.deliveries[-1].review_deadline:
            if (
                capture_allowed(order, now)
                and self.payments.work_allowed(db, order)
                and self.current_dataset_checks(order)
            ):
                self._capture(order, now, db=db)
                return True
            if order.order_state == "delivered" and not any(
                c.status == "open" for c in order.cases
            ):
                self._human(
                    order,
                    "Review expired without current mandatory verification and clear authority.",
                )
                return True
        return False

    def expire_due(self):
        changed = 0
        with self.repository.transaction() as db:
            for order in self.repository.all(db, "order", CatalogOrder):
                if self._advance(order, self.clock(), db=db):
                    order.revision += 1
                    self._save(db, order)
                    changed += 1
            for draft in self.repository.all(db, "request", RequestDraft):
                if self.clock() >= draft.deadline and draft.status not in (
                    "accepted",
                    "human_review",
                ):
                    draft.status, draft.error = "human_review", "Pre-contract deadline expired."
                    draft.revision += 1
                    self.repository.put(db, "request", draft.request_id, draft)
                    if draft.corpus_id.endswith("aggregate-v1"):
                        self.effects.compiled(db, draft)
                    changed += 1
        return changed

    def _capture(self, order, now, *, db=None):
        if not capture_allowed(order, now) or not self.current_dataset_checks(order):
            raise DomainError(409, "capture gates do not pass")
        if self.payments.is_live(order):
            self.payments.reserve_terminal(db, order, "capture")
            return
        key = f"{order.snapshot.order_id}:capture"
        order.ledger = (
            *order.ledger,
            Booking(
                operation_id=key,
                kind="capture",
                amount=order.snapshot.quote.amount,
                binding=order.binding,
                recorded_at=now,
                receipt=mock_receipt(key, "capture"),
            ),
        )
        order.order_state = "closed"
        self.effects.payment(db, order, "capture", order.ledger[-1].receipt)

    def _release(self, order, now, *, db=None):
        if any(b.kind == "capture" for b in order.ledger):
            raise DomainError(
                409, "captured money needs a refund; refund execution is not implemented"
            )
        if order.authorization.status == "released":
            return
        if order.authorization.receipt is None:
            raise DomainError(409, "unfunded payment has no held funds to return")
        if self.payments.is_live(order):
            self.payments.reserve_terminal(db, order, "void")
            return
        key = f"{order.snapshot.order_id}:release"
        order.ledger = (
            *order.ledger,
            Booking(
                operation_id=key,
                kind="release",
                amount=order.snapshot.quote.amount,
                binding=order.binding,
                recorded_at=now,
                receipt=mock_receipt(key, "release"),
            ),
        )
        order.authorization = order.authorization.model_copy(update={"status": "released"})

    def _accept(self, order, command, now, actor, *, db=None):
        if order.order_state != "delivered" or any(
            c.status in ("open", "scope_change", "human_review") for c in order.cases
        ):
            raise DomainError(409, "acceptance requires undisputed delivered work")
        order.customer_acceptance = order.binding
        self._capture(order, now, db=db)

    def _invalidate(self, order):
        order.binding = order.binding.model_copy(
            update={"evidence_revision": order.binding.evidence_revision + 1}
        )
        if order.verification:
            order.verification_history = (*order.verification_history, order.verification)
        order.verification = None
        order.customer_acceptance = None
        order.approvals = tuple(
            a.model_copy(update={"status": "invalidated"}) if a.status == "pending" else a
            for a in order.approvals
        )
        order.jobs = tuple(
            j.model_copy(update={"status": "stale"}) if j.status in ("queued", "running") else j
            for j in order.jobs
        )

    @staticmethod
    def _enqueue(order, kind):
        if any(
            j.binding == order.binding and j.kind == kind and j.status in ("queued", "running")
            for j in order.jobs
        ):
            return
        order.jobs = (*order.jobs, Job(job_id=identifier("job"), kind=kind, binding=order.binding))

    def _dispute(self, order, command, now, actor, *, db=None):
        submitted = self.payments.submitted_capture(db, order)
        if (
            not is_dataset(order)
            and not submitted
            and (
                order.order_state != "delivered"
                or not order.deliveries
                or now >= order.deliveries[-1].review_deadline
            )
        ):
            raise DomainError(409, "dispute requires an active unclosed delivery review")
        if not order.deliveries:
            raise DomainError(409, "a complaint requires a published delivery")
        if any(
            c.complaint.artifact_id == delivery_artifact(order.deliveries[-1]).artifact_id
            for c in order.cases
        ):
            raise DomainError(409, "this delivery already has a dispute case")
        complaint = command.complaint
        if is_dataset(order):
            self.validate_dataset_complaint(order, complaint)
        if complaint.artifact_id != delivery_artifact(
            order.deliveries[-1]
        ).artifact_id or complaint.requirement_id not in {
            r.requirement_id for r in order.snapshot.quote.specification.requirements
        }:
            raise ValueError(
                "complaint must target the current delivery and an accepted requirement"
            )
        order.cases = (
            *order.cases,
            Case(
                case_id=identifier("case"),
                complaint=complaint,
                opened_at=now,
                deadline=now + timedelta(seconds=60),
            ),
        )
        self.effects.disputed(db, order)
        if (
            submitted
            or is_dataset(order)
            and (
                order.ledger or now >= cutoff(order) or now >= order.deliveries[-1].review_deadline
            )
        ):
            self._human(
                order,
                "Late complaint recorded; retain human review and reconcile any submitted payment.",
            )
            return
        self._invalidate(order)
        order.delivery_state = "needs_review"
        self._enqueue(order, "reverify")

    def _answer(self, order, command, now, actor):
        if is_dataset(order):
            raise DomainError(
                422, "dataset answers require the request-bound /runs answer contract"
            )
        case = order.cases[-1] if order.cases else None
        if not case or case.status != "open" or not case.question or now >= case.deadline:
            raise DomainError(409, "no current investigation question")
        order.cases = (
            *order.cases[:-1],
            case.model_copy(update={"answers": (*case.answers, command.text), "question": None}),
        )
        self._invalidate(order)
        self._enqueue(order, "reverify")

    def _retry(self, order, command, now, actor):
        if order.order_state != "operational_failure" or order.free_corrections_used:
            raise DomainError(409, "operational retry is unavailable")
        self._invalidate(order)
        order.order_state, order.error = "processing", None
        self._enqueue(order, "fulfill")

    def _approve_customer(self, order, command, now, actor):
        self._approve(order, command, now, "customer", command.actor)

    def _approve_provider(self, order, command, now, actor):
        self._approve(order, command, now, "provider", actor)

    def _approve(self, order, command, now, role, actor):
        approval = next((a for a in order.approvals if a.approval_id == command.approval_id), None)
        if not approval or approval.status != "pending" or approval.binding != order.binding:
            raise DomainError(409, "approval is stale or no longer pending")
        if not command.accept:
            updated = approval.model_copy(update={"status": "rejected"})
            order.authority_state = "rejected"
            self._human(
                order,
                (
                    "Approval rejected; original contract preserved pending "
                    "release or negotiated offer."
                ),
            )
        else:
            updated = approval.model_copy(update={f"{role}_actor": actor})
            if updated.customer_actor and updated.provider_actor:
                updated = updated.model_copy(update={"status": "approved"})
        order.approvals = tuple(
            updated if a.approval_id == approval.approval_id else a for a in order.approvals
        )
        if updated.status == "approved":
            amendment = next(a for a in order.amendments if a.amendment_id == updated.amendment_id)
            if amendment.classification != "evidence_only":
                raise DomainError(
                    409, "substantive changes require a server offer and separate quote acceptance"
                )
            source = self.registry.identify(amendment.artifact)
            self._apply_repair(order, amendment, source)

    def _review(self, order, command, now, actor, *, db=None):
        if order.order_state != "human_review":
            raise DomainError(409, "reviewer decisions require human review")
        for span in command.supporting_evidence:
            self.store.resolve(span, order.artifacts)
        decision = ReviewerDecision(
            actor=actor,
            action=command.action,
            reason=command.reason,
            supporting_evidence=command.supporting_evidence,
            binding=order.binding,
            recorded_at=now,
            negotiated_exception=command.action == "propose_exception",
        )
        order.decisions = (*order.decisions, decision)
        if command.action == "release_authorization":
            self._release(order, now, db=db)
            if not self.payments.is_live(order):
                order.order_state = "closed"
        elif command.action == "propose_exception":
            order.authority_state = "pending_consent"
            order.error = (
                "Negotiated exception proposed; original facts unchanged. "
                "New customer/provider agreement required."
            )
        else:
            if (
                now >= order.authorization.expires_at
                or len(order.evidence_requests) >= self.policy.evidence_attempts
            ):
                raise DomainError(409, "evidence budget or authorization expired")
            if order.repair_deadline and now >= order.repair_deadline:
                raise DomainError(409, "evidence repair deadline cannot be extended")
            self._request_evidence(order, now)

    def _request_evidence(self, order, now):
        if len(order.evidence_requests) >= self.policy.evidence_attempts:
            self._human(order, "Evidence repair attempts exhausted.")
            return
        if any(not r.answered for r in order.evidence_requests):
            order.order_state = "waiting_evidence"
            return
        open_case = next((c for c in order.cases if c.status == "open"), None)
        if open_case and open_case.questions_asked >= self.policy.max_questions:
            self._human(
                order, "Dispute question budget exhausted; evidence repair cannot add rounds."
            )
            return
        report = order.verification
        candidates = (
            [
                a
                for a in report.assessments
                if a.obligation_id in report.material_blockers and a.requested_evidence
            ]
            if report
            else []
        )
        if not candidates:
            # An unresolved amendment has its own evidence findings.
            candidates = [
                a
                for amendment in order.amendments
                for a in amendment.assessment
                if a.requested_evidence
            ]
        if not candidates:
            self._human(order, "Material evidence unresolved without a useful specific request.")
            return
        finding = candidates[0]
        if finding.reason_code in ("SOURCE_AUTHORITY_UNVERIFIED", "EFFECTIVE_DATE_CONFLICT"):
            order.authority_state = "pending_source_authority"
        source = next(
            (s for s in order.sources if finding.obligation_id.startswith(s.source_id)),
            order.sources[0],
        )
        amendment = next(
            (
                a
                for a in reversed(order.amendments)
                if finding.obligation_id == f"amendment/{a.amendment_id}"
            ),
            None,
        )
        if amendment:
            source = next(s for s in order.sources if s.source_id == amendment.target_source_id)
        if order.repair_deadline is None:
            order.repair_deadline = now + timedelta(seconds=self.policy.evidence_repair_seconds)
        deadline = min(
            order.repair_deadline,
            order.authorization.expires_at,
            *(c.deadline for c in order.cases if c.status == "open"),
        )
        if now >= deadline:
            self._human(order, "Evidence repair deadline expired.")
            return
        order.evidence_requests = (
            *order.evidence_requests,
            EvidenceRequest(
                request_id=identifier("evidence"),
                obligation_ids=(finding.obligation_id,),
                target_source=source,
                prompt=finding.requested_evidence,
                round=len(order.evidence_requests) + 1,
                deadline=deadline,
            ),
        )
        if open_case:
            order.cases = tuple(
                c.model_copy(update={"questions_asked": c.questions_asked + 1, "question": None})
                if c.case_id == open_case.case_id
                else c
                for c in order.cases
            )
        order.order_state = "waiting_evidence"

    def upload(self, order_id, command):
        # Authorize the narrow request before storing bytes; parse outside the DB lock.
        fingerprint = self.repository.fingerprint("upload", command)
        self.get(order_id)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, order_id, command.idempotency_key, fingerprint, CatalogOrder
            )
            if replay:
                return replay
            current = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check(current, command)
            if is_dataset(current):
                raise DomainError(
                    422, "Use the versioned run evidence-answer endpoint for datasets"
                )
            pending = next(
                (
                    r
                    for r in current.evidence_requests
                    if r.request_id == command.evidence_request_id
                ),
                None,
            )
            if (
                not pending
                or pending.answered
                or self.clock() >= pending.deadline
                or current.order_state != "waiting_evidence"
            ):
                raise DomainError(409, "upload must answer a current evidence request")
        try:
            data = base64.b64decode(command.pdf_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 PDF") from exc
        artifact = self.store.put(data)
        self.get(order_id)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, order_id, command.idempotency_key, fingerprint, CatalogOrder
            )
            if replay:
                return replay
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check(order, command)
            request = next(
                (r for r in order.evidence_requests if r.request_id == command.evidence_request_id),
                None,
            )
            if (
                not request
                or request.answered
                or self.clock() >= request.deadline
                or order.order_state != "waiting_evidence"
            ):
                raise DomainError(409, "upload must answer a current, unexpired evidence request")
            amendment = Amendment(
                amendment_id=identifier("amendment"),
                actor=command.actor,
                target_source_id=request.target_source.source_id,
                target_version=request.target_source.version,
                evidence_request_id=request.request_id,
                reason=command.reason,
                artifact=artifact,
                relationship=command.relationship,
                submitted_at=self.clock(),
                history=("Submitted for assessment",),
            )
            order.amendments = (*order.amendments, amendment)
            order.artifacts = tuple(dict.fromkeys((*order.artifacts, artifact)))
            order.evidence_requests = tuple(
                r.model_copy(update={"answered": True}) if r.request_id == request.request_id else r
                for r in order.evidence_requests
            )
            self._invalidate(order)
            order.order_state = "processing"
            self._enqueue(order, "reverify")
            order.revision += 1
            self._save(db, order)
            self._remember_order(db, order_id, command.idempotency_key, fingerprint, order)
            return order

    def _apply_repair(self, order, amendment, source):
        if source is None:
            raise ValueError("repair lacks registered authority")
        order.sources = tuple(
            source if s.source_id == amendment.target_source_id else s for s in order.sources
        )
        self._invalidate(order)
        order.amendments = tuple(
            a.model_copy(
                update={
                    "applied_revision": order.binding.evidence_revision,
                    "history": (
                        *a.history,
                        "Applied under accepted source authority; dependent findings invalidated",
                    ),
                }
            )
            if a.amendment_id == amendment.amendment_id
            else a
            for a in order.amendments
        )
        order.authority_state, order.order_state = "clear", "processing"
        self._enqueue(order, "reverify" if order.deliveries else "fulfill")

    def offer(self, order_id, command, *, actor):
        self.get(order_id)
        fingerprint = self.repository.fingerprint(f"offer:{actor}", command)
        with self.repository.transaction() as db:
            replay = self.repository.replay(
                db, order_id, command.idempotency_key, fingerprint, Quote
            )
            if replay:
                return replay
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check(order, command)
            if self.clock() >= order.authorization.expires_at:
                raise DomainError(409, "original authority expired; human resolution required")
            if is_dataset(order):
                raise DomainError(422, "Use the versioned run offer endpoint for datasets")
            sources = order.sources
            purpose = "additional_work"
            if command.amendment_id:
                amendment = next(
                    (a for a in order.amendments if a.amendment_id == command.amendment_id), None
                )
                if (
                    not amendment
                    or amendment.classification != "substantive"
                    or order.authority_state != "pending_consent"
                ):
                    raise DomainError(409, "substantive amendment is not pending")
                replacement = self.registry.identify(amendment.artifact, db)
                if replacement is None:
                    raise DomainError(409, "amendment lacks registered source authority")
                sources = tuple(
                    replacement if s.source_id == amendment.target_source_id else s for s in sources
                )
                purpose = "substantive_amendment"
            if command.terms.corpus_id != order.snapshot.quote.specification.terms.corpus_id:
                raise ValueError("offer must remain within selected provider corpus")
            quote = Quote(
                quote_id=identifier("quote"),
                request_id=order.snapshot.quote.request_id,
                request_revision=order.revision,
                specification=specification(
                    command.terms,
                    order.revision,
                    command.work_description,
                    order.snapshot.quote.specification.limitations,
                ),
                sources=sources,
                amount=self.price(purpose),
                payment_terms=self.payments.terms(
                    self.price(purpose),
                    order.snapshot.quote.payment_terms.payment_info.payer,
                    self.clock(),
                ),
                expires_at=min(
                    self.clock() + timedelta(seconds=120),
                    order.authorization.expires_at,
                    order.repair_deadline or order.authorization.expires_at,
                ),
                purpose=purpose,
                work_description=command.work_description,
                parent_order_id=order_id,
                parent_binding=order.binding,
                amendment_id=command.amendment_id,
                provider_actor=actor,
            )
            self.repository.put(db, "quote", quote.quote_id, quote)
            self.repository.remember(db, order_id, command.idempotency_key, fingerprint, quote)
            return quote

    def claim_job(self, order_id):
        self.get(order_id)
        with self.repository.transaction() as db:
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            now = self.clock()
            if (
                order.schema_version < 4
                or order.order_state
                in ("human_review", "closed", "pending_approval", "waiting_evidence")
                or not self.payments.work_allowed(db, order)
                or not authorization_ready(order.authorization)
                or now >= order.authorization.expires_at
            ):
                raise DomainError(
                    409,
                    "work dispatch requires active successful authorization and lifecycle gates",
                )
            candidate = next(
                (
                    j
                    for j in order.jobs
                    if j.binding == order.binding
                    and (j.status == "queued" or j.status == "running" and j.lease_until <= now)
                ),
                None,
            )
            if candidate is None:
                raise DomainError(409, "no dispatchable work")
            if is_dataset(order) and not fits(
                order, now, "dispatch" if candidate.kind != "reverify" else "publication"
            ):
                self._human(
                    order,
                    (
                        "Insufficient capture budget for full work, review, dispute and "
                        "permitted correction windows."
                    ),
                )
                order.revision += 1
                self._save(db, order)
                return order, None
            if candidate.attempts >= 3:
                self._human(order, "Durable worker retry budget exhausted.")
                order.revision += 1
                self._save(db, order)
                return order, None
            job = candidate.model_copy(
                update={
                    "status": "running",
                    "attempts": candidate.attempts + 1,
                    "lease_token": identifier("lease"),
                    "lease_until": now + timedelta(seconds=45),
                }
            )
            order.jobs = tuple(job if j.job_id == job.job_id else j for j in order.jobs)
            if is_dataset(order) and candidate.status == "running":
                self.reclaim_dataset_assessment(db, order)
            order.revision += 1
            self._save(db, order)
            self.effects.job(db, order, job)
            return order, job

    def _check_job(self, order, job, *, db=None):
        current = next((j for j in order.jobs if j.job_id == job.job_id), None)
        if (
            current is None
            or current.status != "running"
            or current.lease_token != job.lease_token
            or current.binding != order.binding
            or self.clock() >= current.lease_until
            or order.order_state in ("human_review", "closed", "pending_approval")
            or not self.payments.work_allowed(db, order)
        ):
            raise DomainError(409, "worker lease or evidence binding is stale")
        if self.clock() >= order.authorization.expires_at:
            raise DomainError(409, "authorization expired while worker was running")

    @staticmethod
    def _finish_job(order, job, status="done", error=None):
        order.jobs = tuple(
            j.model_copy(update={"status": status, "error": error}) if j.job_id == job.job_id else j
            for j in order.jobs
        )

    def run_one(self, order_id):
        order, job = self.claim_job(order_id)
        if job is None:
            return order
        if is_dataset(order):
            return self.run_dataset(order, job)
        pending = next((a for a in order.amendments if a.classification == "pending"), None)
        try:
            if pending:
                target = next(s for s in order.sources if s.source_id == pending.target_source_id)
                classification, assessments, source = assess_amendment(
                    pending,
                    target,
                    self.registry,
                    self.store,
                    order.snapshot.quote.specification.terms,
                )
                return self.complete_amendment(
                    order_id, job, pending, classification, assessments, source
                )
            context = FulfillmentContext(
                snapshot=order.snapshot, binding=order.binding, sources=order.sources
            )
            report, extracted = verify(context, self.store, self.clock())
            pdf = sidecar = None
            if report.passed:
                if job.kind == "reverify" and order.deliveries:
                    pdf = order.deliveries[-1].pdf
                    report, _ = verify(
                        context,
                        self.store,
                        self.clock(),
                        delivery=pdf,
                        stage="dispute"
                        if order.cases and order.cases[-1].status == "open"
                        else "delivery",
                    )
                else:
                    pdf, sidecar = produce(
                        extracted, order.snapshot.quote.specification.terms, self.store
                    )
                    next_binding = order.binding.model_copy(
                        update={"delivery_version": len(order.deliveries) + 1}
                    )
                    context = context.model_copy(update={"binding": next_binding})
                    report, _ = verify(
                        context, self.store, self.clock(), delivery=pdf, stage="delivery"
                    )
            semantic = None
            if (
                order.cases
                and order.cases[-1].status == "open"
                and report.passed
                and order.cases[-1].complaint.intent != "change_scope"
            ):
                semantic = self.investigator.investigate(
                    DisputeContext(
                        fulfillment=context, delivery=order.deliveries[-1], case=order.cases[-1]
                    ),
                    report,
                    self.store,
                )
            return self.complete_verification(order_id, job, report, pdf, sidecar, semantic)
        except DomainError:
            raise
        except Exception as exc:
            # Persist operational failure without pretending that a file or refund exists.
            return self.fail_job(order_id, job, f"{type(exc).__name__}: {exc}")

    def fail_job(self, order_id, job, reason):
        with self.repository.transaction() as db:
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check_job(order, job, db=db)
            self._finish_job(order, job, "failed", reason)
            order.order_state, order.delivery_state, order.error = (
                "operational_failure",
                "operational_failure",
                reason,
            )
            if job.kind == "correct" or order.free_corrections_used:
                self._human(order, "The free correction failed operationally.")
            order.revision += 1
            self._save(db, order)
            return order

    def complete_amendment(self, order_id, job, amendment, classification, assessments, source):
        self.get(order_id)
        with self.repository.transaction() as db:
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check_job(order, job, db=db)
            for assessment in assessments:
                for span in (*assessment.citations, *assessment.conflicting_evidence):
                    self.store.resolve(span, order.artifacts)
            updated = amendment.model_copy(
                update={
                    "classification": classification,
                    "assessment": assessments,
                    "history": (*amendment.history, f"Assessed: {classification}"),
                }
            )
            order.amendments = tuple(
                updated if a.amendment_id == amendment.amendment_id else a for a in order.amendments
            )
            self._finish_job(order, job)
            if classification == "evidence_only":
                if (
                    order.snapshot.quote.specification.terms.source_policy.evidence_repair
                    == "preauthorized"
                ):
                    self._apply_repair(order, updated, source)
                else:
                    order.authority_state, order.order_state = "pending_consent", "pending_approval"
                    order.approvals = (
                        *order.approvals,
                        Approval(
                            approval_id=identifier("approval"),
                            amendment_id=amendment.amendment_id,
                            binding=order.binding,
                            reason=(
                                "Accepted source policy requires customer and provider "
                                "approval of evidence repair."
                            ),
                        ),
                    )
            elif classification == "substantive":
                order.authority_state, order.order_state = "pending_consent", "pending_approval"
                order.error = (
                    "Substantive change requires a provider offer and customer "
                    "acceptance; original agreement unchanged."
                )
            else:
                self._request_evidence(order, self.clock())
            order.revision += 1
            self._save(db, order)
            return order

    def _reserve_correction(self, order):
        if is_dataset(order) and not fits(order, self.clock(), "correction"):
            self._human(
                order,
                "Insufficient capture budget for correction and full fresh review/dispute windows.",
            )
            return
        if order.free_corrections_used:
            self._human(order, "Further provider defect after the single free correction.")
            return
        order.free_corrections_used = 1
        self._invalidate(order)
        order.order_state, order.delivery_state = "processing", "needs_review"
        self._enqueue(order, "correct")

    def complete_verification(self, order_id, job, report, pdf=None, sidecar=None, semantic=None):
        self.get(order_id)
        with self.repository.transaction() as db:
            order = self.repository.load(db, "order", order_id, CatalogOrder)
            self._check_job(order, job, db=db)
            publishes = sidecar is not None
            expected = (
                order.binding.model_copy(update={"delivery_version": len(order.deliveries) + 1})
                if publishes
                else order.binding
            )
            if report.binding != expected:
                raise DomainError(409, "verification result has stale binding")
            additions = tuple(a for a in (pdf, sidecar) if a)
            evidence = tuple(dict.fromkeys((*order.artifacts, *additions)))
            for assessment in report.assessments:
                for span in (*assessment.citations, *assessment.conflicting_evidence):
                    self.store.resolve(span, evidence)
            self._finish_job(order, job)
            # Keep immutable evidence. Dataset downloads separately enforce safe-count validation.
            order.artifacts = evidence
            if order.verification:
                order.verification_history = (*order.verification_history, order.verification)
            # Failed generated PDFs are retained as evidence, not published customer deliveries.
            if publishes and not report.passed:
                report = report.model_copy(update={"binding": order.binding})
            order.verification = report
            now = self.clock()
            published = False
            if publishes and is_dataset(order) and not fits(order, now, "publication"):
                order.verification = report.model_copy(update={"binding": order.binding})
                self._human(
                    order,
                    (
                        "Delivery cannot be published: full review/dispute/correction "
                        "budget no longer fits."
                    ),
                )
            elif report.provider_defect:
                if order.cases and order.cases[-1].status == "open":
                    order.cases = (
                        *order.cases[:-1],
                        order.cases[-1].model_copy(update={"status": "supported"}),
                    )
                self._reserve_correction(order)
            elif report.material_blockers:
                self._request_evidence(order, now)
            elif not report.passed:
                self._human(
                    order,
                    "Source constraints cannot be satisfied; provider fault is not established.",
                )
            else:
                if publishes:
                    order.binding = expected
                    delivery_type = DatasetDelivery if is_dataset(order) else Delivery
                    files = (
                        {"csv": pdf, "preview": sidecar}
                        if is_dataset(order)
                        else {"pdf": pdf, "sidecar": sidecar}
                    )
                    delivery = delivery_type(
                        version=len(order.deliveries) + 1,
                        **files,
                        published_at=now,
                        review_deadline=now + timedelta(seconds=60),
                        binding=expected,
                    )
                    order.deliveries = (*order.deliveries, delivery)
                    published = True
                    order.customer_acceptance = None
                order.order_state, order.delivery_state = "delivered", "verified"
                order.repair_deadline = None
                if order.cases and order.cases[-1].status == "open":
                    if is_dataset(order):
                        self.resolve_dataset_complaint(db, order, semantic)
                    else:
                        self._resolve_complaint(order, semantic)
                if capture_allowed(order, now):
                    self._capture(order, now, db=db)
            order.revision += 1
            self._save(db, order)
            self.effects.verified(db, order, job, report, published)
            return order

    def _resolve_complaint(self, order, semantic=None):
        case = order.cases[-1]
        if semantic:
            order.semantic_findings = (*order.semantic_findings, semantic)
        if case.complaint.intent == "change_scope":
            updated = case.model_copy(update={"status": "scope_change"})
            order.authority_state, order.order_state = "pending_consent", "pending_approval"
            order.error = (
                "Scope change requires an explicit offer; the original contract remains unchanged."
            )
            # Consent is bounded by the original investigation deadline.
            order.repair_deadline = case.deadline
        elif semantic and semantic.result == "FAIL":
            updated = case.model_copy(update={"status": "unsupported"})
            order.error = f"Unsupported complaint: {semantic.explanation} No complaint fee."
        elif semantic and semantic.result == "PASS":
            # Tool/model disagreement needs review. Agreement is not independent ground truth.
            self._human(
                order, "Semantic evidence supports a claim despite passing tools; review required."
            )
            return
        elif case.answers and "scope" in case.answers[-1].lower():
            updated = case.model_copy(update={"status": "scope_change"})
            order.authority_state, order.order_state = "pending_consent", "pending_approval"
            order.repair_deadline = case.deadline
        else:
            # Passing fixture tools alone cannot refute a broad semantic claim.
            if case.questions_asked >= 2:
                self._human(
                    order, "Claim remains unresolved after two answered investigation rounds."
                )
                return
            updated = case.model_copy(
                update={
                    "questions_asked": case.questions_asked + 1,
                    "question": (
                        semantic.requested_evidence
                        if semantic and semantic.requested_evidence
                        else f"For {case.complaint.product_id}, provide the source passage "
                        "supporting "
                        f"{case.complaint.field}, or state whether you want changed scope."
                    ),
                }
            )
        order.cases = (*order.cases[:-1], updated)

    def human_review_table(self, order):
        return review_table(order, self.store)

    def view(self, order, *, db=None):
        if db is None:
            with self.repository.transaction() as read_db:
                return self.view(order, db=read_db)
        actions = []
        payment = self.payments.view(db, order)
        if (
            payment
            and payment.payment.state == "awaiting_signature"
            and order.order_state == "awaiting_authorization"
            and self.clock().timestamp() < payment.payment.terms.payment_info.pre_approval_expiry
        ):
            actions.extend(("prepare_funding", "submit_funding_authorization"))
        if order.order_state == "delivered":
            if capture_allowed(
                order.model_copy(update={"customer_acceptance": order.binding}), self.clock()
            ):
                actions.append("accept")
            if self.clock() < order.deliveries[-1].review_deadline and not any(
                case.complaint.artifact_id == delivery_artifact(order.deliveries[-1]).artifact_id
                for case in order.cases
            ):
                actions.append("dispute")
        if order.cases and order.cases[-1].question and order.cases[-1].status == "open":
            actions.append("answer")
        if order.order_state == "waiting_evidence":
            actions.append("upload_evidence")
        if any(a.status == "pending" for a in order.approvals):
            actions.append("approve_amendment")
        if payment and payment.payment.terms.mode == "base_sepolia":
            if payment.payment.state != "funded":
                actions = [
                    a
                    for a in actions
                    if a not in ("accept", "upload_evidence", "approve_amendment", "answer")
                ]
            if (
                any(
                    o.intent.action == "capture" and o.state in ("submitted", "uncertain")
                    for o in payment.operations
                )
                and order.deliveries
                and not any(
                    c.complaint.artifact_id == delivery_artifact(order.deliveries[-1]).artifact_id
                    for c in order.cases
                )
                and "dispute" not in actions
            ):
                actions.append("dispute")
            if not self.payments._parent_returned(db, payment.payment):
                actions = []
        if order.schema_version < 4:
            actions = []
        return OrderView(
            order=order,
            server_time=self.clock(),
            available_actions=tuple(actions),
            human_review=self.human_review_table(order),
            payment=payment,
            payment_mode=payment.payment.terms.mode if payment else "mock",
        )
