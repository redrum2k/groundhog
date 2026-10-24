"""Read-only event facade and bound commands over the integrated funded lifecycle."""

import json
from datetime import timedelta

from app.catalog.requirements import specification
from app.contracts.catalog import (
    CatalogOrder,
    DatasetEvidenceAnswer,
    Quote,
    RequestCommand,
    RequestDraft,
    ReviewerDecision,
)
from app.contracts.dataset import BrokeragePolicy
from app.contracts.models import Money
from app.contracts.runs import ActionAvailability, DecisionAcknowledgement, RunCreated, RunPage
from app.datasets import make_terms, seed_registry
from app.orders.catalog import identifier
from app.orders.dataset_evidence import evidence_request, resolve_current_reference
from app.orders.run_events import binding
from app.orders.service import DomainError
from app.runtime.catalog_policy import authorization_ready
from app.runtime.dataset_policy import cutoff


class Runs:
    def __init__(self, service):
        self.service = service
        self.repository = service.repository
        self.events = service.effects.log

    def create(self, command, key):
        seed_registry(self.service.registry, self.service.store)
        draft = self.service.create_request(
            RequestCommand(**command.model_dump(), idempotency_key=key)
        )
        return RunCreated(id=draft.request_id)

    def order(self, db, run_id):
        order_id = self.events.identity(db, run_id)
        if not order_id:
            raise DomainError(409, "run has no accepted order")
        return self.repository.load(db, "order", order_id, CatalogOrder)

    @staticmethod
    def check(order, expected, run_id):
        if expected != binding(order) or expected.runId != run_id:
            raise DomainError(
                409, "run/order/snapshot or delivery/evidence/revision changed; review again"
            )

    def reviewer_actions(self, db, order):
        now = self.service.clock()
        reviewing = order.order_state == "human_review"
        payment = self.service.payments.view(db, order)
        terminal = self.service.payments.journal.terminal(db, order.payment_id)
        releasable = (
            reviewing
            and order.authorization.receipt is not None
            and not order.ledger
            and not terminal
            and payment.payment.state in ("funded", "failed", "expired_not_returned")
        )
        case = order.cases[-1] if order.cases else None
        ask = (
            reviewing
            and now < cutoff(order)
            and (
                case is not None
                and case.questions_asked < 2
                and not case.question
                and now < case.deadline
                or case is None
                and order.verification is not None
                and bool(order.verification.material_blockers)
                and len(order.evidence_requests) < 2
                and not any(not r.answered for r in order.evidence_requests)
                and (not order.repair_deadline or now < order.repair_deadline)
            )
        )
        return [
            ActionAvailability(
                action="approve",
                enabled=releasable,
                reason=(
                    "Approve the proposed return of uncaptured funds; accepted scope "
                    "and findings stay unchanged."
                )
                if releasable
                else (
                    "No eligible release remedy is proposed; approval cannot "
                    "authorize capture or rewrite scope."
                ),
            ),
            ActionAvailability(
                action="reject",
                enabled=reviewing,
                reason="Reject the proposed remedy and retain human review; no purchase or fee.",
            ),
            ActionAvailability(
                action="ask",
                enabled=ask,
                reason="Request one bounded evidence answer within the original deadline."
                if ask
                else "Question budget, pending answer or deadline prevents another request.",
            ),
            ActionAvailability(
                action="escalate",
                enabled=reviewing,
                reason="Retain human review for Maya/CFO with the current evidence.",
            ),
        ]

    def page(self, run_id, after=0, limit=100):
        with self.repository.transaction() as db:
            events, high = self.events.page(db, run_id, after, limit)
            draft = self.repository.load(db, "request", run_id, RequestDraft)
            order_id = self.events.identity(db, run_id)
            order = self.repository.load(db, "order", order_id, CatalogOrder) if order_id else None
            quotes = [q for q in self.repository.all(db, "quote", Quote) if q.request_id == run_id]
            quote = max(quotes, key=lambda q: q.expires_at) if quotes else None
            next_after = events[-1].seq if events else after
            caught_up = next_after == high
            actions = []
            payment = None
            if order:
                view = self.service.view(order, db=db)
                payment = view.payment
                actions = [
                    ActionAvailability(
                        action=a,
                        enabled=True,
                        reason="Current accepted lifecycle permits this action.",
                    )
                    for a in view.available_actions
                ]
                # Late complaints remain recordable even when payment cannot settle.
                if (
                    order.deliveries
                    and not order.cases
                    and not any(a.action == "dispute" for a in actions)
                ):
                    actions.append(
                        ActionAvailability(
                            action="dispute",
                            enabled=True,
                            reason=(
                                "Late complaint is recorded for human review; it cannot cancel "
                                "submitted settlement."
                            ),
                        )
                    )
                actions += self.reviewer_actions(db, order)
            elif draft.status == "clarification":
                actions = [
                    ActionAvailability(
                        action="clarify",
                        enabled=True,
                        reason="Answer the current question; original deadline is unchanged.",
                    )
                ]
            elif draft.status == "ready":
                actions = [
                    ActionAvailability(
                        action="quote", enabled=True, reason="Request a frozen server quote."
                    )
                ]
                if quote and quote.purpose != "initial":
                    actions = []
                if quote and self.service.clock() < quote.expires_at:
                    actions.append(
                        ActionAvailability(
                            action="accept_quote",
                            enabled=True,
                            reason="Explicitly accept the displayed quote; funding is separate.",
                        )
                    )
            return RunPage(
                events=events,
                next_after=next_after,
                high_watermark=high,
                caught_up=caught_up,
                server_time=self.service.clock(),
                binding=binding(order) if order else None,
                available_actions=actions if caught_up else [],
                request=draft,
                quote=quote,
                payment=payment,
                reviewClosesAt=order.deliveries[-1].review_deadline
                if order and order.deliveries
                else None,
                disputeClosesAt=order.cases[-1].deadline if order and order.cases else None,
                captureClosesAt=order.authorization.expires_at if order else None,
                latestSafeSubmissionAt=cutoff(order) if order else None,
                evidence_request=evidence_request(order, self.service.store, self.service.clock())
                if order and caught_up
                else None,
                complaint_targets=self.service.complaint_targets(order)
                if order and caught_up
                else (),
            )

    def decide(self, run_id, command, key, actor):
        scope = f"run-decisions:{run_id}:{actor}"
        fingerprint = self.repository.fingerprint("review", command)
        with self.repository.transaction() as db:
            replay = self.repository.replay(db, scope, key, fingerprint, DecisionAcknowledgement)
            if replay:
                return replay
            order = self.order(db, run_id)
            self.check(order, command.binding, run_id)
            available = {a.action: a for a in self.reviewer_actions(db, order)}
            if not available[command.action].enabled:
                raise DomainError(409, available[command.action].reason)
            cited = []
            for (body,) in db.execute("SELECT body FROM run_events WHERE run_id=?", (run_id,)):
                from app.contracts.runs import EVENT_ADAPTER

                event = EVENT_ADAPTER.validate_json(body)
                if event.type == "evidence_found" and event.evidence.id in command.evidence_ids:
                    source = event.evidence.source
                    if source.kind != "cell" or source.reference is None:
                        raise DomainError(
                            422, "review evidence must resolve to current registered dataset bytes"
                        )
                    self.service.store.resolve(source.reference, order.artifacts)
                    cited.append(source.reference)
            if command.evidence_ids and len(cited) != len(command.evidence_ids):
                raise DomainError(422, "unknown or duplicate evidence reference")
            if not cited and order.verification:
                cited = list(
                    dict.fromkeys(r for a in order.verification.assessments for r in a.citations)
                )[:8]
            for ref in cited:
                self.service.store.resolve(ref, order.artifacts)
            now = self.service.clock()
            decision_id = identifier("decision")
            mapped = (
                "release_authorization"
                if command.action == "approve"
                else "request_evidence"
                if command.action == "ask"
                else command.action
            )
            order.decisions = (
                *order.decisions,
                ReviewerDecision(
                    actor=actor,
                    action=mapped,
                    reason=command.reason,
                    supporting_evidence=tuple(cited),
                    binding=order.binding,
                    recorded_at=now,
                ),
            )
            if command.action == "approve":
                self.service._release(order, now, db=db)
                if not self.service.payments.is_live(order):
                    order.order_state = "closed"
            elif command.action == "ask":
                if order.cases:
                    case = order.cases[-1]
                    question = (
                        "Which frozen source and exact cell establish the disputed "
                        "definition or missing ZIP?"
                    )
                    order.cases = (
                        *order.cases[:-1],
                        case.model_copy(
                            update={
                                "status": "open",
                                "questions_asked": case.questions_asked + 1,
                                "question": question,
                            }
                        ),
                    )
                    order.order_state = "delivered" if order.deliveries else "waiting_evidence"
                    self.service.effects.message(
                        db, run_id, decision_id + ":question", question, step="investigate"
                    )
                else:
                    self.service._request_evidence(order, now)
            else:
                order.error = (
                    "Reviewer rejected the proposed remedy: "
                    if command.action == "reject"
                    else "Escalated to Maya/CFO: "
                ) + command.reason
            order.revision += 1
            self.service._save(db, order)
            self.service.effects.emit(
                db,
                order,
                decision_id,
                type="controller_decided",
                step="decide",
                action=command.action,
                by=actor,
                note=command.reason,
                binding=command.binding.model_dump(),
            )
            acknowledgement = DecisionAcknowledgement(decision_id=decision_id)
            self.repository.remember(db, scope, key, fingerprint, acknowledgement)
            return acknowledgement

    def answer(self, run_id, command, key):
        scope = f"run-answer:{run_id}"
        fingerprint = self.repository.fingerprint("answer", command)
        if command.request_id is None:
            historical = json.loads(fingerprint)
            historical["payload"].pop("request_id")
            fingerprint = json.dumps(historical, sort_keys=True)
        with self.repository.transaction() as db:
            replay = self.repository.replay(db, scope, key, fingerprint, DecisionAcknowledgement)
            if replay:
                return replay
            order = self.order(db, run_id)
            self.check(order, command.binding, run_id)
            now = self.service.clock()
            if now >= cutoff(order):
                raise DomainError(409, "evidence cannot extend capture authority")
            request = evidence_request(order, self.service.store, now)
            if not request or command.request_id != request.request_id:
                raise DomainError(409, "answer does not target the current evidence request")
            if len(set(command.references)) != len(command.references):
                raise DomainError(422, "answer references must be unique")
            for ref in command.references:
                resolve_current_reference(order, ref, self.service.store)
            case = order.cases[-1] if order.cases else None
            pending = next((r for r in order.evidence_requests if not r.answered), None)
            if case and case.status == "open" and case.question and now < case.deadline:
                order.cases = (
                    *order.cases[:-1],
                    case.model_copy(
                        update={"answers": (*case.answers, command.text), "question": None}
                    ),
                )
            elif pending and now < pending.deadline:
                if not command.references:
                    raise DomainError(
                        422, "source-evidence repair needs a resolving registered reference"
                    )
                order.evidence_requests = tuple(
                    r.model_copy(update={"answered": True})
                    if r.request_id == pending.request_id
                    else r
                    for r in order.evidence_requests
                )
            else:
                raise DomainError(409, "no current bounded evidence request")
            order.evidence_answers = (
                *order.evidence_answers,
                DatasetEvidenceAnswer(
                    answer_id=f"answer:{key}",
                    request_id=request.request_id,
                    case_id=request.case_id,
                    actor=order.snapshot.customer_actor,
                    original_binding=order.binding,
                    original_revision=order.revision,
                    received_at=now,
                    text=command.text,
                    references=command.references,
                ),
            )
            # Evidence citations do not change source editions, values or accepted terms.
            self.service._invalidate(order)
            # Earlier semantic effects remain in append-only events, not current findings.
            order.semantic_findings = ()
            order.order_state = "processing"
            self.service._enqueue(order, "reverify")
            order.revision += 1
            self.service._save(db, order)
            self.service.effects.message(
                db, run_id, f"answer:{key}", command.text, speaker="buyer", step="investigate"
            )
            ack = DecisionAcknowledgement(decision_id=f"answer:{key}")
            self.repository.remember(db, scope, key, fingerprint, ack)
            return ack

    def offer(self, run_id, command, key, actor):
        scope = f"run-offer:{run_id}:{actor}"
        fingerprint = self.repository.fingerprint("offer", command)
        with self.repository.transaction() as db:
            replay = self.repository.replay(db, scope, key, fingerprint, Quote)
            if replay:
                return replay
            order = self.order(db, run_id)
            self.check(order, command.binding, run_id)
            if self.service.clock() >= cutoff(order) or not authorization_ready(
                order.authorization
            ):
                raise DomainError(409, "additional work needs current parent authority")
            original = order.snapshot.quote.specification.terms
            if command.scope == "yoga" and (
                original.category == "gym_app_or_yoga"
                or any(a.result == "PASS" for a in order.semantic_findings)
            ):
                raise DomainError(
                    409, "yoga already owed under the accepted agreement is not billable expansion"
                )
            corpus = "oakland-aggregate-v1" if command.scope == "oakland" else original.corpus_id
            sources = self.service.registry.manifest(corpus, db)
            run = identifier("request")
            terms = make_terms(
                sources,
                self.service.store,
                category="gym_app_or_yoga" if command.scope == "yoga" else original.category,
                request_id=run,
            )
            purpose = (
                "substantive_amendment" if command.scope == "replacement" else "additional_work"
            )
            if purpose == "substantive_amendment":
                if order.ledger or self.service.payments.submitted_capture(db, order):
                    raise DomainError(409, "replacement requires uncaptured parent funds")
                order.authority_state = "pending_consent"
                order.revision += 1
                self.service._save(db, order)
            amount = Money(
                amount_minor={"oakland": 6000, "yoga": 3000, "replacement": 12000}[command.scope],
                currency="USD",
                decimals=2,
            )
            now = self.service.clock()
            spec = specification(
                terms,
                1,
                f"Separately offered {command.scope} aggregate dataset",
                ("Synthetic demo pricing; buyer acceptance and separate funding required.",),
            )
            draft = RequestDraft(
                request_id=run,
                prompt=spec.summary,
                corpus_id=corpus,
                created_at=now,
                deadline=now + timedelta(seconds=120),
                status="ready",
                specification=spec,
            )
            self.repository.put(db, "request", run, draft)
            self.service.effects.created(db, draft)
            quote = Quote(
                quote_id=identifier("quote"),
                request_id=run,
                request_revision=1,
                specification=spec,
                sources=sources,
                amount=amount,
                payment_terms=self.service.payments.terms(
                    amount, order.snapshot.quote.payment_terms.payment_info.payer, now
                ),
                policy=BrokeragePolicy(),
                expires_at=min(now + timedelta(seconds=120), cutoff(order)),
                purpose=purpose,
                work_description=spec.summary,
                parent_order_id=order.snapshot.order_id,
                parent_binding=order.binding,
                provider_actor=actor,
            )
            self.repository.put(db, "quote", quote.quote_id, quote)
            self.service.effects.quoted(db, quote)
            self.repository.remember(db, scope, key, fingerprint, quote)
            return quote

    def resolve(self, run_id, evidence_id):
        with self.repository.transaction() as db:
            self.events.identity(db, run_id)
            from app.contracts.runs import EVENT_ADAPTER

            for (body,) in db.execute("SELECT body FROM run_events WHERE run_id=?", (run_id,)):
                event = EVENT_ADAPTER.validate_json(body)
                if event.type == "evidence_found" and event.evidence.id == evidence_id:
                    source = event.evidence.source
                    if source.kind == "cell" and source.reference:
                        order = self.order(db, run_id)
                        value = self.service.store.resolve(source.reference, order.artifacts)
                        return {
                            "kind": "cell",
                            "reference": source.reference.model_dump(),
                            "value": value,
                        }
                if event.type == "message" and event.message.id == evidence_id:
                    return {"kind": "message", "message": event.message.model_dump(by_alias=True)}
            raise DomainError(404, "evidence reference not found")
