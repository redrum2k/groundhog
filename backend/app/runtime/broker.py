"""Broker profile adapter over the existing identities, artifact store and OrderService."""

import base64
import binascii
import json
import os
from datetime import timedelta

from app.contracts.api import (
    CreateOrder,
    Mutation,
    OpenDispute,
    PublishDelivery,
    ReportFailure,
    ScopeObligation,
)
from app.contracts.broker import (
    BrokerAmendment,
    BrokerQuestion,
    BrokerRecord,
    DraftQuestion,
    HumanTask,
    IntakeDraft,
    IntentMessage,
)
from app.contracts.data_product import Parameters
from app.contracts.models import (
    AcceptedDataAmendment,
    AcceptedPolicy,
    CaseState,
    DataVerification,
    DeliveryState,
    EvidencePointer,
    EvidenceReference,
    OrderSnapshot,
    OrderState,
)
from app.data_products import (
    DIMENSIONS,
    FIELDS,
    QUESTION_TEXT,
    build_package,
    delivery_checks,
    effective_specification,
    evidence_digest,
    make_specification,
    missing_fields,
    parse_source,
    source_pin,
    specification_digest,
)
from app.runtime.jobflow_policy import require
from app.storage import broker as storage
from app.storage import improvement as improvements
from app.storage.jobflow import DomainError, canonical, digest, uid

BROKER_POLICY = AcceptedPolicy(policy_version="broker-review-v0.3", overall_case_seconds=1800)


def reference(metadata, kind, derived_from=()):
    return EvidenceReference(
        evidence_id=metadata["id"],
        version=metadata["version"],
        sha256=metadata["sha256"],
        storage_key=f"jobflow/{metadata['id']}",
        media_type=metadata["media_type"],
        kind=kind,
        derived_from=tuple(derived_from),
    )


class Broker:
    def __init__(
        self,
        jobflow,
        *,
        producer=build_package,
        dispute_assessor=None,
        dispute_assessment_enabled=None,
    ):
        self.jobflow = jobflow
        self.store, self.base, self.clock = jobflow.store, jobflow.base, jobflow.clock
        self.producer = producer
        self.dispute_assessor = dispute_assessor
        self.dispute_assessment_enabled = (
            os.getenv("ENABLE_BROKER_DISPUTE_ASSESSMENT") == "true"
            if dispute_assessment_enabled is None
            else dispute_assessment_enabled
        )
        storage.migrate(self.store)
        improvements.migrate(self.store)

    def _emit(self, db, record, actor, causal, event_type, **payload):
        return storage.event(
            db,
            record.id,
            actor.id if hasattr(actor, "id") else actor,
            causal,
            self.clock(),
            event_type,
            revision=record.revision,
            **payload,
        )

    def _receipt(self, db, actor, request, envelope, record):
        self.store.receipt(
            db, actor.id, request.idempotency_key, envelope, record.model_dump(mode="json")
        )
        return record

    def _clarify(self, db, draft, actor, causal):
        template = improvements.template(
            db, draft.customer_id, draft.product_id, draft.template_version
        )
        draft.validator_bindings = {
            dimension: recipe
            for dimension, (recipe, _) in DIMENSIONS.items()
            if recipe in template.get("validators", ())
        }
        draft.template_approved_by = template.get("approved_by")
        missing = missing_fields(draft.parameters)
        for field in template["required_fields"]:
            if field in missing and not any(
                q.field == field and q.answer_id is None for q in draft.questions
            ):
                question = DraftQuestion(
                    id=uid("spec-question"),
                    field=field,
                    prompt=template["questions"].get(field, QUESTION_TEXT[field]),
                )
                draft.questions.append(question)
                self._emit(
                    db,
                    draft,
                    actor,
                    causal,
                    "spec.question_requested",
                    question=question.model_dump(mode="json"),
                    template_version=draft.template_version,
                )
        draft.unresolved_fields = missing
        if draft.sources:
            draft.specification = make_specification(draft)
        draft.provider_accepted_digest = None
        draft.customer_accepted_digest = None
        draft.acceptance_digest = None
        draft.provider_capability = "UNREVIEWED"
        draft.status = "CLARIFYING" if missing or not draft.sources else "READY"
        unasked = [field for field in missing if field not in template["required_fields"]]
        if unasked:
            improvements.incident(
                db,
                entity_id=draft.id,
                customer_id=draft.customer_id,
                product_id=draft.product_id,
                template_version=draft.template_version,
                cause="MISSING_SPECIFICATION",
                unknowns=unasked,
                now=self.clock(),
                sources=draft.sources,
                questions=tuple(q.prompt for q in draft.questions),
            )
            if not any(task.state == "OPEN" for task in draft.human_tasks):
                draft.human_tasks.append(
                    HumanTask(
                        id=uid("intake-task"),
                        issue_id=draft.id,
                        reason="Current intake has no approved question for material terms.",
                        missing_facts=unasked,
                        evidence=list(draft.sources),
                        binding=None,
                        next_action=(
                            "Ask a scoped clarification for each missing field; "
                            "never invent its value."
                        ),
                        created_at=self.clock(),
                    )
                )
        for task in draft.human_tasks:
            if task.state == "OPEN":
                task.missing_facts = [field for field in task.missing_facts if field in missing]
                if not task.missing_facts:
                    task.state, task.resolved_at = "RESOLVED", self.clock()

    def create_draft(self, actor, request):
        require(actor, roles={"customer"})
        envelope = {"route": "broker.draft.create", "body": request.model_dump(mode="json")}
        with self.store.connect(write=True) as db:
            replay = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if replay is not None:
                return IntakeDraft.model_validate(replay)
            if request.parent_order_id:
                parent = storage.get(db, "br_orders", request.parent_order_id, BrokerRecord)
                require(actor, parent)
            template = improvements.template(db, actor.customer_id, request.product_id)
            draft = IntakeDraft(
                id=uid("broker"),
                customer_id=actor.customer_id,
                product_id=request.product_id,
                template_version=template["id"],
                created_at=self.clock(),
                parent_order_id=request.parent_order_id,
                messages=[
                    IntentMessage(
                        id=uid("intent"),
                        actor_id=actor.id,
                        text=request.intent,
                        created_at=self.clock(),
                    )
                ],
            )
            self._emit(
                db,
                draft,
                actor,
                request.idempotency_key,
                "spec.draft_created",
                template_version=draft.template_version,
                parent_order_id=draft.parent_order_id,
            )
            self._clarify(db, draft, actor, request.idempotency_key)
            storage.save(db, "br_drafts", draft)
            return self._receipt(db, actor, request, envelope, draft)

    def draft(self, actor, draft_id):
        with self.store.connect() as db:
            draft = storage.get(db, "br_drafts", draft_id, IntakeDraft)
            require(actor, draft)
            return draft

    def draft_command(self, actor, draft_id, request):
        envelope = {
            "route": "broker.draft.command",
            "id": draft_id,
            "body": request.model_dump(mode="json"),
        }
        with self.store.connect(write=True) as db:
            draft = storage.get(db, "br_drafts", draft_id, IntakeDraft)
            require(actor, draft)
            replay = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if replay is not None:
                return IntakeDraft.model_validate(replay)
            if request.expected_revision != draft.revision:
                raise DomainError("Draft revision is stale")
            if draft.status in {"ACCEPTED", "DECLINED"}:
                raise DomainError("An accepted or declined draft cannot be rewritten")
            draft.revision += 1
            if request.verb == "clarify_intake":
                require(actor, roles={"controller"})
                if request.field not in draft.unresolved_fields or any(
                    q.field == request.field and q.answer_id is None for q in draft.questions
                ):
                    raise DomainError("Manual clarification must address an unasked material field")
                question = DraftQuestion(
                    id=uid("spec-question"),
                    field=request.field,
                    prompt=QUESTION_TEXT[request.field],
                )
                draft.questions.append(question)
                self._emit(
                    db,
                    draft,
                    actor,
                    request.idempotency_key,
                    "spec.question_requested",
                    question=question.model_dump(mode="json"),
                    company_staff_touches=1,
                    measured_staff_seconds=None,
                    template_version=draft.template_version,
                )
            elif request.verb == "answer_intake":
                require(actor, roles={"customer"})
                question = next(
                    (
                        q
                        for q in draft.questions
                        if q.id == request.question_id and q.answer_id is None
                    ),
                    None,
                )
                if question is None:
                    raise DomainError("The exact intake question is not open")
                if request.value is None:
                    raise DomainError(
                        "Supply a concrete answer or explicitly decline the draft", 422
                    )
                values = draft.parameters.model_dump(mode="json")
                values[question.field] = request.value
                draft.parameters = Parameters.model_validate(values)
                answer = IntentMessage(
                    id=uid("answer"),
                    actor_id=actor.id,
                    field=question.field,
                    text=request.text or canonical(request.value),
                    created_at=self.clock(),
                )
                draft.messages.append(answer)
                draft.questions = [
                    q.model_copy(update={"answer_id": answer.id}) if q.id == question.id else q
                    for q in draft.questions
                ]
                self._emit(
                    db,
                    draft,
                    actor,
                    request.idempotency_key,
                    "spec.answer_received",
                    question_id=question.id,
                    answer_id=answer.id,
                )
                self._clarify(db, draft, actor, request.idempotency_key)
            elif request.verb == "offer":
                require(actor, roles={"provider"})
                if request.capability is None or request.price is None:
                    raise DomainError("Provider offer requires explicit capability and price", 422)
                if request.price.currency != "USDSIM" or request.price.decimals != 2:
                    raise DomainError("This profile uses mock USDSIM minor units only", 422)
                draft.provider_capability, draft.offered_price = request.capability, request.price
                draft.provider_reason = request.text
                if request.capability == "UNSUPPORTED":
                    draft.status = "UNSUPPORTED"
                    self._emit(
                        db,
                        draft,
                        actor,
                        request.idempotency_key,
                        "spec.unsupported",
                        reason=request.text,
                    )
                elif draft.unresolved_fields or not draft.sources:
                    draft.status = "CLARIFYING"
                    self._emit(
                        db,
                        draft,
                        actor,
                        request.idempotency_key,
                        "spec.acceptance_blocked",
                        missing=draft.unresolved_fields,
                        owner="controller",
                        next_action="Clarify every material term before any payment authorization",
                    )
                else:
                    draft.specification = make_specification(draft)
                    draft.acceptance_digest = digest(
                        {
                            "specification": draft.specification.model_dump(mode="json"),
                            "price": request.price.model_dump(mode="json"),
                            "policy": BROKER_POLICY.model_dump(mode="json"),
                        }
                    )
                    draft.provider_accepted_digest = draft.acceptance_digest
                    draft.provider_actor_id = actor.id
                    draft.status = "READY"
                    self._emit(
                        db,
                        draft,
                        actor,
                        request.idempotency_key,
                        "spec.provider_accepted",
                        digest=draft.acceptance_digest,
                    )
            elif request.verb == "accept_specification":
                require(actor, roles={"customer"})
                if (
                    draft.status != "READY"
                    or not draft.acceptance_digest
                    or draft.unresolved_fields
                    or request.digest != draft.acceptance_digest
                    or draft.provider_accepted_digest != request.digest
                    or draft.provider_capability != "SUPPORTED"
                    or request.authorization_expires_at is None
                ):
                    raise DomainError(
                        "Acceptance requires both parties' exact complete "
                        "specification, price and policy"
                    )
                self._accept_draft(db, draft, actor, request)
            elif request.verb == "decline":
                require(actor, roles={"customer"})
                draft.status = "DECLINED"
                self._emit(
                    db,
                    draft,
                    actor,
                    request.idempotency_key,
                    "spec.declined",
                    parent_order_id=draft.parent_order_id,
                )
            else:
                raise DomainError("Command does not apply to an intake draft", 422)
            storage.save(db, "br_drafts", draft)
            return self._receipt(db, actor, request, envelope, draft)

    def _accept_draft(self, db, draft, actor, request, *, historical_import=False):
        if historical_import:
            draft.template_version = draft.specification.template_version
        metadata = storage.artifact(
            db,
            draft.id,
            canonical(
                {
                    "specification": draft.specification.model_dump(mode="json"),
                    "price": draft.offered_price.model_dump(mode="json"),
                    "policy": BROKER_POLICY.model_dump(mode="json"),
                    "customer": actor.id,
                    "provider": draft.provider_actor_id,
                    "digest": draft.acceptance_digest,
                }
            ).encode(),
            "accepted-specification.json",
            "application/json",
            actor.id,
            self.clock(),
            "accepted_input",
        )
        source_ids = []
        inputs = [reference(metadata, "accepted_input")]
        for row in db.execute(
            "SELECT id,metadata,raw FROM jf_artifacts WHERE order_id=?", (draft.id,)
        ):
            meta = json.loads(row["metadata"])
            if meta["kind"] == "source" and source_pin(bytes(row["raw"])) in draft.sources:
                inputs.append(reference(meta, "accepted_input"))
                source_ids.append(row["id"])
        snapshot = OrderSnapshot(
            job_type="regional_market_intelligence",
            order_id=draft.id,
            snapshot_id=f"{draft.id}:accepted:{draft.acceptance_digest}",
            accepted_at=self.clock(),
            accepted_brief=draft.messages[0].text,
            input_versions=tuple(inputs),
            price=draft.offered_price,
            policy=BROKER_POLICY,
            data_specification=draft.specification,
        )
        base = self.base.create(
            CreateOrder(
                snapshot=snapshot,
                authorization_expires_at=request.authorization_expires_at,
                idempotency_key=request.idempotency_key,
            ),
            connection=db,
        )
        record = BrokerRecord(
            id=draft.id,
            draft_id=draft.id,
            customer_id=draft.customer_id,
            original_specification=draft.specification,
            source_artifact_ids=source_ids,
            messages=list(draft.messages),
            overall_case_deadline=self.clock() + timedelta(minutes=30),
            parent_order_id=draft.parent_order_id,
            base_order=self.base.view(base),
        )
        draft.order_id = record.id
        draft.customer_accepted_digest = request.digest
        draft.status = "ACCEPTED"
        storage.save(db, "br_orders", record)
        self._emit(
            db,
            record,
            actor,
            request.idempotency_key,
            "spec.accepted",
            digest=request.digest,
            template_version=draft.template_version,
            snapshot_id=snapshot.snapshot_id,
            policy="broker-review-v0.3",
            authorization_id=base.authorization_id,
            mode="SIMULATED",
            historical_import=historical_import,
        )
        if not historical_import:
            improvements.record_outcome(
                db,
                record.id,
                record.customer_id,
                draft.product_id,
                "ACCEPTED_AFTER_CLARIFICATION",
                self.clock(),
            )

    def upload(self, actor, entity_id, request, *, accepted=False):
        require(actor, roles={"provider"})
        try:
            raw = base64.b64decode(request.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise DomainError("Invalid source encoding", 422) from exc
        source, pin = parse_source(raw), source_pin(raw)
        envelope = {
            "route": "broker.source",
            "accepted": accepted,
            "id": entity_id,
            "body": request.model_dump(mode="json"),
        }
        with self.store.connect(write=True) as db:
            table, model = ("br_orders", BrokerRecord) if accepted else ("br_drafts", IntakeDraft)
            record = storage.get(db, table, entity_id, model)
            require(actor, record)
            replay = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if replay is not None:
                return model.model_validate(replay)
            if record.revision != request.expected_revision:
                raise DomainError("Source upload is stale")
            if not accepted and record.status in {"ACCEPTED", "DECLINED"}:
                raise DomainError("Accepted source versions cannot be overwritten")
            if accepted and len(record.source_artifact_ids) >= 32:
                raise DomainError("Source acquisition bound reached; human review required")
            for row in db.execute(
                "SELECT metadata,raw FROM jf_artifacts WHERE order_id=?", (entity_id,)
            ):
                meta = json.loads(row[0])
                if meta["kind"] == "source":
                    existing = source_pin(bytes(row[1]))
                    if (existing.source_id, existing.version) == (source.source_id, source.version):
                        raise DomainError(
                            "Source ID/version already exists; new evidence needs a new version"
                        )
            meta = storage.artifact(
                db,
                entity_id,
                raw,
                request.filename,
                "application/json",
                actor.id,
                self.clock(),
                "source",
            )
            record.revision += 1
            if accepted:
                record.source_artifact_ids.append(meta["id"])
                base = self.base.repository.get(db, record.id)
                base.evidence = (*base.evidence, reference(meta, "verification_report"))
                if base.binding:
                    self.base._new_binding(base)
                base.delivery_state = DeliveryState.NEEDS_REVIEW
                base.revision += 1
                self.base.repository.save(db, base)
                self._project(record, base)
            else:
                record.sources = [p for p in record.sources if p.source_id != pin.source_id] + [pin]
                self._clarify(db, record, actor, request.idempotency_key)
            self._emit(
                db,
                record,
                actor,
                request.idempotency_key,
                "evidence.source_added",
                source=pin.model_dump(mode="json"),
                artifact_id=meta["id"],
                authority="COMPANY_RECORD",
            )
            storage.save(db, table, record)
            return self._receipt(db, actor, request, envelope, record)

    def _source_bytes(self, db, record, specification):
        sources = []
        for identifier in record.source_artifact_ids:
            raw, _, _ = self.store.artifact(db, record.id, identifier)
            if source_pin(raw) in specification.sources:
                sources.append(raw)
        return sources

    def _project(self, record, base):
        record.base_order = self.base.view(base)
        if base.delivery_state == DeliveryState.OPERATIONAL_FAILURE:
            record.colour, record.owner, record.next_action = (
                "red",
                "provider",
                base.failure or "Inspect provider failure",
            )
            if base.order_state == OrderState.HUMAN_REVIEW:
                record.owner = "controller"
                record.next_action = "Resolve the persistent human task; correction is exhausted"
        elif base.order_state == OrderState.HUMAN_REVIEW:
            record.colour, record.owner, record.next_action = (
                "orange",
                "controller",
                "Resolve the persistent human task",
            )
        elif base.order_state == OrderState.CLOSED:
            record.colour, record.owner, record.next_action = (
                "green",
                "customer",
                "Review the evidence-backed mock settlement",
            )
        elif (
            base.data_verification
            and base.data_verification.verdict == "PASS"
            and base.case_state != CaseState.OPEN
        ):
            record.colour, record.owner, record.next_action = (
                "green",
                "customer",
                "Accept the verified delivery or dispute within review",
            )
        elif base.regeneration_pending:
            record.colour, record.owner, record.next_action = (
                "orange",
                "provider",
                "Produce the one permitted free correction",
            )
        else:
            record.colour = "orange"
            question = next((q for q in reversed(record.questions) if q.status == "OPEN"), None)
            record.owner = question.recipient if question else "provider"
            record.next_action = (
                question.text
                if question
                else "Produce or investigate the current accepted specification"
            )

    def _human_task(self, db, record, base, reason, causal="deadline"):
        current = next((task for task in record.human_tasks if task.state == "OPEN"), None)
        missing = (
            [
                check.explanation
                for check in base.data_verification.checks
                if check.verdict != "PASS"
            ]
            if base.data_verification
            else [reason]
        )
        if current is None:
            current = HumanTask(
                id=uid("human-task"),
                issue_id=record.issue_id or base.case_id or record.id,
                reason=reason,
                missing_facts=missing,
                evidence=list(effective_specification(base, self.clock()).sources),
                binding=base.binding,
                created_at=self.clock(),
            )
            record.human_tasks.append(current)
            self._emit(
                db,
                record,
                "system",
                causal,
                "case.escalated",
                task=current.model_dump(mode="json"),
                issue_id=current.issue_id,
            )
        else:
            current.binding = base.binding
            current.reason = reason
            current.missing_facts = missing
            current.evidence = list(effective_specification(base, self.clock()).sources)
        if base.payment_phase != "booked" and self.clock() >= base.authorization_expires_at:
            current.next_action = (
                "Request an explicitly authorized payment renewal from the payment owner; "
                "this workflow cannot auto-renew expired authority."
            )
        elif base.payment_state in {"submitted", "uncertain"}:
            current.next_action = (
                "Reconcile the existing payment operation with the payment owner; "
                "do not submit another capture."
            )
        elif self.clock() >= record.overall_case_deadline:
            current.next_action = (
                "Review the evidence and arrange an authorized human remedy; "
                "automated case time is exhausted."
            )
        record.resolution = "HUMAN_REVIEW"
        for question in record.questions:
            if question.status == "OPEN":
                question.status = "CANCELLED"
        return current

    def _sync(self, db, record):
        base = self.base.repository.get(db, record.id)
        prior_revision = record.base_order.order.revision if record.base_order else None
        if (
            self.clock() >= record.overall_case_deadline
            and base.order_state not in {OrderState.CLOSED, OrderState.HUMAN_REVIEW}
            and (record.issue_id or base.regeneration_pending)
        ):
            self.base._hold(
                base, "Overall case deadline reached; further work requires human review"
            )
            base.revision += 1
            self.base.repository.save(db, base)
        if self.base._advance(base, self.clock()):
            base.revision += 1
            self.base.repository.save(db, base)
        if base.order_state == OrderState.HUMAN_REVIEW:
            self._human_task(
                db, record, base, base.failure or "Current evidence requires human review"
            )
        if prior_revision != base.revision:
            record.revision += 1
            self._emit(
                db,
                record,
                "system",
                f"base-{base.revision}",
                "financial.state_changed",
                base_revision=base.revision,
                payment_phase=base.payment_phase,
                order_state=base.order_state,
            )
        self._project(record, base)
        return base

    def view(self, actor, order_id):
        with self.store.connect(write=True) as db:
            record = storage.get(db, "br_orders", order_id, BrokerRecord)
            require(actor, record)
            self._sync(db, record)
            storage.save(db, "br_orders", record)
            return record

    def _base_mutation(self, base, request):
        return dict(
            expected_revision=base.revision,
            expected_binding=base.binding,
            idempotency_key=f"broker:{request.idempotency_key}",
        )

    def _verify(self, db, record, base, actor, causal, *, resume=False):
        if not base.deliveries or not base.binding:
            raise DomainError("Verification requires an actual delivered package")
        specification = effective_specification(base, self.clock())
        artifacts = []
        for ref in (*base.deliveries[-1].artifacts, *base.deliveries[-1].structured_data):
            raw, meta, _ = self.store.artifact(db, record.id, ref.evidence_id)
            if meta["sha256"] != ref.sha256 or meta["version"] != ref.version:
                raise DomainError("Delivery bytes no longer match the frozen reference")
            artifacts.append((meta["filename"], meta["media_type"], raw, ref.evidence_id))
        checks = delivery_checks(
            specification, self._source_bytes(db, record, specification), artifacts
        )
        source_artifacts = {}
        for identifier in record.source_artifact_ids:
            raw, _, _ = self.store.artifact(db, record.id, identifier)
            pin = source_pin(raw)
            source_artifacts[(pin.source_id, pin.version, pin.sha256)] = identifier
        checks = tuple(
            check.model_copy(
                update={
                    "citations": tuple(
                        citation.model_copy(
                            update={
                                "artifact_id": source_artifacts.get(
                                    (citation.source_id, citation.version, citation.sha256),
                                    citation.source_id,
                                )
                            }
                        )
                        for citation in check.citations
                    )
                }
            )
            for check in checks
        )
        for question in record.questions:
            if question.status == "OPEN" and (
                question.binding != base.binding
                or question.specification_sha256 != specification_digest(specification)
            ):
                question.status = "CANCELLED"
                self._emit(
                    db,
                    record,
                    actor,
                    causal,
                    "question.cancelled",
                    question_id=question.id,
                    issue_id=question.issue_id,
                    reason="Evidence or effective specification changed",
                )
        previous_verification = base.data_verification
        base.data_verification = DataVerification(
            proposal=base.binding,
            specification_sha256=specification_digest(specification),
            evidence_sha256=evidence_digest(base),
            verified_at=self.clock(),
            checks=checks,
        )
        self._emit(
            db,
            record,
            actor,
            causal,
            "verification.completed",
            binding=base.binding.model_dump(mode="json"),
            verdict=base.data_verification.verdict,
            specification_sha256=specification_digest(specification),
        )
        if self.dispute_assessment_enabled and base.complaint and record.issue_id:
            # Global PASS is not refutation of an arbitrary complaint. Assessment
            # runs only after this command commits; never inside the DB transaction.
            if (
                base.case_state == CaseState.RESOLVED
                and previous_verification
                and previous_verification.proposal == base.binding
                and previous_verification.specification_sha256
                == specification_digest(specification)
                and previous_verification.evidence_sha256 == evidence_digest(base)
            ):
                # A new idempotency key is not new evidence and cannot reopen a
                # resolved issue or consume its correction again.
                base.revision += 1
                self.base.repository.save(db, base)
                return base
            base.case_state = CaseState.OPEN
            record.resolution = None
            base.delivery_state = DeliveryState.NEEDS_REVIEW
            if base.payment_phase != "booked":
                base.payment_phase = "held"
            base.revision += 1
            self.base.repository.save(db, base)
            return base
        if base.data_verification.verdict == "PASS":
            base.delivery_state = DeliveryState.PASSED
            base.failure = None
            if base.payment_phase != "booked":
                base.payment_phase = "open"
            base.scope_obligations = tuple(
                item.model_copy(update={"fulfilled": True})
                if item.effective_at <= self.clock()
                else item
                for item in base.scope_obligations
            )
            if record.issue_id or base.complaint:
                base.case_state = CaseState.RESOLVED
                record.resolution = "NO_REMEDY" if base.complaint else "CORRECTED"
            if resume:
                base.order_state = OrderState.DELIVERED
                base.review_requires_customer_acceptance = True
                base.review_deadline = None
            for question in record.questions:
                if question.status == "OPEN":
                    question.status = "CANCELLED"
            self._emit(
                db,
                record,
                actor,
                causal,
                "review.opened",
                deadline=base.review_deadline.isoformat() if base.review_deadline else None,
                requires_customer_acceptance=base.review_requires_customer_acceptance,
                resolution=record.resolution,
            )
            improvements.record_outcome(
                db,
                record.id,
                record.customer_id,
                specification.product_id,
                "EVIDENCE_RESOLVED",
                self.clock(),
                binding=base.binding,
            )
        elif base.data_verification.verdict == "FAIL":
            base.delivery_state = DeliveryState.NEEDS_REVIEW
            if not base.regeneration_pending:
                self.base.reserve_free_regeneration(base)
            if base.order_state == OrderState.HUMAN_REVIEW:
                self._human_task(db, record, base, base.failure, causal)
            self._emit(
                db,
                record,
                actor,
                causal,
                "correction.required",
                remaining=0 if base.free_regenerations_used else 1,
                reserved=base.regeneration_pending,
            )
        else:
            base.delivery_state = DeliveryState.NEEDS_REVIEW
            if base.payment_phase != "booked":
                base.payment_phase = "held"
            record.issue_id = record.issue_id or uid("issue")
            base.case_state = CaseState.OPEN
            gaps = [check for check in checks if check.verdict == "UNKNOWN"]
            for gap in gaps:
                improvements.incident(
                    db,
                    entity_id=record.id,
                    customer_id=record.customer_id,
                    product_id=specification.product_id,
                    template_version=specification.template_version,
                    cause=gap.cause,
                    unknowns=[gap.explanation],
                    now=self.clock(),
                    sources=specification.sources,
                    binding=base.binding,
                    issue_id=record.issue_id,
                    specification_sha256=specification_digest(specification),
                    questions=tuple(q.text for q in record.questions),
                )
            if (
                record.question_count >= 2
                or resume
                or self.clock() >= record.overall_case_deadline
                or any(gap.cause in {"UNSUPPORTED_SUBJECTIVE", "VALIDATOR_FAILURE"} for gap in gaps)
            ):
                self.base._hold(
                    base, "Material evidence remains unresolved; authorized human judgment required"
                )
                self._human_task(db, record, base, base.failure, causal)
            elif not any(q.status == "OPEN" for q in record.questions):
                gap = gaps[0]
                recipient = "customer" if gap.cause == "MISSING_SPECIFICATION" else "provider"
                question = BrokerQuestion(
                    id=uid("question"),
                    issue_id=record.issue_id,
                    requirement_id=gap.requirement_id,
                    text=(
                        "Please clarify this term; both parties must accept changed terms: "
                        if recipient == "customer"
                        else "Please supply the authenticated source revision for this fact: "
                    )
                    + gap.explanation[:400],
                    recipient=recipient,
                    binding=base.binding,
                    specification_sha256=specification_digest(specification),
                )
                record.questions.append(question)
                record.question_count += 1
                self._emit(
                    db,
                    record,
                    actor,
                    causal,
                    "question.requested",
                    issue_id=record.issue_id,
                    question=question.model_dump(mode="json"),
                )
        base.revision += 1
        self.base.repository.save(db, base)
        return base

    def _produce(self, db, record, base, actor, request):
        require(actor, roles={"provider"})
        if base.order_state not in {OrderState.PROCESSING, OrderState.FAILED}:
            raise DomainError("Production requires initial work or a reserved correction")
        specification = effective_specification(base, self.clock())
        sources = self._source_bytes(db, record, specification)
        try:
            package = self.producer(specification, sources)
            if len(package) != 3 or {item[0] for item in package} != {
                "source-methodology.pdf",
                "market-sidecar.json",
                "market-data.csv"
                if any(r.parameters.output_format == "csv" for r in specification.requirements)
                else "market-data.json",
            }:
                raise ValueError(
                    "Provider did not return the required data, PDF and sidecar package"
                )
            metadata = [
                storage.artifact(
                    db, record.id, raw, filename, media, actor.id, self.clock(), "delivery_artifact"
                )
                for filename, media, raw in package
            ]
            delivered = tuple(reference(item, "delivery_artifact") for item in metadata[:2])
            sidecar = reference(
                metadata[2],
                "structured_data",
                tuple(
                    EvidencePointer(
                        evidence_id=item.evidence_id, version=item.version, sha256=item.sha256
                    )
                    for item in delivered
                ),
            )
            base = self.base.mutate(
                record.id,
                "delivery",
                PublishDelivery(
                    **self._base_mutation(base, request),
                    artifacts=delivered,
                    structured_data=(sidecar,),
                ),
                connection=db,
            )
            record.delivery_artifact_ids = [item["id"] for item in metadata]
            self._emit(
                db,
                record,
                actor,
                request.idempotency_key,
                "delivery.published",
                delivery_version=base.binding.delivery_version,
                artifact_ids=record.delivery_artifact_ids,
            )
            return self._verify(db, record, base, actor, request.idempotency_key)
        except (ValueError, TypeError, KeyError) as exc:
            if base.order_state == OrderState.FAILED:
                base.order_state = OrderState.PROCESSING
            self.base._failure(
                base,
                ReportFailure(
                    **self._base_mutation(base, request),
                    error_code="DATA_PROVIDER_FAILURE",
                    message=str(exc)[:1200],
                ),
                self.clock(),
            )
            base.revision += 1
            self.base.repository.save(db, base)
            self._emit(
                db, record, actor, request.idempotency_key, "delivery.failed", error=base.failure
            )
            if base.order_state == OrderState.HUMAN_REVIEW:
                self._human_task(db, record, base, base.failure, request.idempotency_key)
            return base

    def command(self, actor, order_id, request):
        with self.store.connect() as db:
            replay = self.store.replay(
                db,
                actor.id,
                request.idempotency_key,
                {
                    "route": "broker.command",
                    "id": order_id,
                    "body": request.model_dump(mode="json"),
                },
            )
        result = self._command(actor, order_id, request)
        if (
            replay is None
            and self.dispute_assessment_enabled
            and request.verb
            in {
                "investigate",
                "answer",
                "resolve_human",
            }
        ):
            from app.runtime.dispute_assessment import run_assessment

            run_assessment(
                self,
                actor,
                order_id,
                request.idempotency_key,
                resume=request.verb == "resolve_human" and request.decision == "RESUME",
            )
        # Immutable command receipt acknowledges acquisition; read current outcome
        # from the existing event stream/order. Replays return the identical receipt.
        return result

    def _command(self, actor, order_id, request):
        self.view(actor, order_id)
        envelope = {
            "route": "broker.command",
            "id": order_id,
            "body": request.model_dump(mode="json"),
        }
        with self.store.connect(write=True) as db:
            record = storage.get(db, "br_orders", order_id, BrokerRecord)
            require(actor, record)
            replay = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if replay is not None:
                return BrokerRecord.model_validate(replay)
            if record.revision != request.expected_revision:
                raise DomainError("Order revision is stale; refetch current evidence")
            base = self.base.repository.get(db, order_id)
            record.revision += 1
            match request.verb:
                case "produce":
                    base = self._produce(db, record, base, actor, request)
                case "accept_delivery":
                    require(actor, roles={"customer"})
                    base = self.base.mutate(
                        order_id,
                        "accept",
                        Mutation(**self._base_mutation(base, request)),
                        connection=db,
                    )
                    self._emit(
                        db,
                        record,
                        actor,
                        request.idempotency_key,
                        "review.accepted",
                        base_revision=base.revision,
                    )
                case "dispute":
                    require(actor, roles={"customer"})
                    if not request.text:
                        raise DomainError("A dispute must state the contested requirement", 422)
                    base = self.base.mutate(
                        order_id,
                        "dispute",
                        OpenDispute(**self._base_mutation(base, request), complaint=request.text),
                        connection=db,
                    )
                    record.issue_id = uid("issue")
                    self._emit(
                        db,
                        record,
                        actor,
                        request.idempotency_key,
                        "case.opened",
                        issue_id=record.issue_id,
                        deadline=base.review_deadline.isoformat(),
                    )
                case "investigate":
                    require(actor, roles={"investigator", "controller"})
                    if base.order_state == OrderState.HUMAN_REVIEW:
                        raise DomainError("Resolve the persistent human task to resume")
                    base = self._verify(db, record, base, actor, request.idempotency_key)
                case "answer":
                    question = next(
                        (q for q in record.questions if q.id == request.question_id), None
                    )
                    if (
                        question is None
                        or question.status != "OPEN"
                        or question.binding != base.binding
                    ):
                        raise DomainError("Question is missing, closed or stale")
                    require(actor, roles={question.recipient})
                    if not request.text or base.order_state == OrderState.HUMAN_REVIEW:
                        raise DomainError(
                            "An active question and nonempty bounded answer are required"
                        )
                    if question.specification_sha256 != specification_digest(
                        effective_specification(base, self.clock())
                    ):
                        raise DomainError("Question predates the operative accepted specification")
                    answer = IntentMessage(
                        id=uid("answer"),
                        actor_id=actor.id,
                        text=request.text,
                        created_at=self.clock(),
                    )
                    record.messages.append(answer)
                    question.status, question.answer_id = "ANSWERED", answer.id
                    meta = storage.artifact(
                        db,
                        record.id,
                        answer.model_dump_json().encode(),
                        "answer.json",
                        "application/json",
                        actor.id,
                        self.clock(),
                        "customer_evidence",
                    )
                    base.evidence = (*base.evidence, reference(meta, "customer_evidence"))
                    self.base._new_binding(base)
                    self._emit(
                        db,
                        record,
                        actor,
                        request.idempotency_key,
                        "answer.received",
                        question_id=question.id,
                        issue_id=question.issue_id,
                        answer_id=answer.id,
                        authority="PARTY_ASSERTION",
                    )
                    base = self._verify(db, record, base, actor, request.idempotency_key)
                    self._emit(
                        db,
                        record,
                        actor,
                        request.idempotency_key,
                        "case.resumed",
                        issue_id=question.issue_id,
                        question_id=question.id,
                    )
                case "resolve_human":
                    require(actor, roles={"controller"})
                    task = next(
                        (
                            task
                            for task in record.human_tasks
                            if task.id == request.task_id and task.state == "OPEN"
                        ),
                        None,
                    )
                    if (
                        task is None
                        or task.binding != base.binding
                        or not request.decision
                        or not request.text
                    ):
                        raise DomainError(
                            "A current human task, explicit decision and explanation are required"
                        )
                    self._emit(
                        db,
                        record,
                        actor,
                        request.idempotency_key,
                        "human.decision",
                        task_id=task.id,
                        decision=request.decision,
                        company_staff_touches=1,
                        measured_staff_seconds=None,
                        explanation=request.text,
                    )
                    task.decision, task.decided_by = request.decision, actor.id
                    if request.decision == "RESUME":
                        if base.payment_state in {"submitted", "uncertain"}:
                            raise DomainError(
                                "Reconcile the original payment operation before resuming"
                            )
                        if (
                            base.payment_phase != "booked"
                            and self.clock() >= base.authorization_expires_at
                        ) or self.clock() >= record.overall_case_deadline:
                            raise DomainError(
                                "Resume needs valid authority and a live overall case; "
                                "no automatic renewal"
                            )
                        base = self._verify(
                            db, record, base, actor, request.idempotency_key, resume=True
                        )
                        if base.order_state != OrderState.HUMAN_REVIEW:
                            task.state, task.resolved_at = "RESOLVED", self.clock()
                            self._emit(
                                db,
                                record,
                                actor,
                                request.idempotency_key,
                                "case.resumed",
                                issue_id=task.issue_id,
                                task_id=task.id,
                            )
                case "propose_amendment" | "accept_amendment":
                    base = self._amend(db, record, base, actor, request)
                case _:
                    raise DomainError("Command does not apply to an accepted order", 422)
            self._project(record, base)
            storage.save(db, "br_orders", record)
            return self._receipt(db, actor, request, envelope, record)

    def _amend(self, db, record, base, actor, request):
        require(actor, roles={"customer", "provider"})
        if base.payment_phase == "booked":
            raise DomainError("Additional work after settlement requires a separate accepted quote")
        if request.verb == "propose_amendment":
            if (
                request.specification is None
                or request.effective_at is None
                or request.effective_at < self.clock()
            ):
                raise DomainError(
                    "Amendment needs an explicit future effective time and full specification"
                )
            old, new = effective_specification(base, self.clock()), request.specification
            if (
                new.product_id != old.product_id
                or new.template_version != old.template_version
                or new.original_intent != old.original_intent
                or new.version <= old.version
                or {r.id for r in new.requirements} != {r.id for r in old.requirements}
            ):
                raise DomainError("New product/requirements require a separate scope quote")
            if any(
                amendment.specification.version >= new.version for amendment in record.amendments
            ):
                raise DomainError("Amendment specification versions must increase monotonically")
            if any(
                amendment.effective_at > request.effective_at for amendment in base.data_amendments
            ):
                raise DomainError(
                    "A new amendment cannot reorder previously accepted effective dates"
                )
            for original in old.requirements:
                candidate = next(r for r in new.requirements if r.id == original.id)
                if (candidate.recipe, candidate.dimension) != (original.recipe, original.dimension):
                    raise DomainError("An amendment cannot swap validator semantics")
                for field in FIELDS:
                    prior = getattr(original.parameters, field)
                    if (
                        prior is not None
                        and prior != ()
                        and getattr(candidate.parameters, field) != prior
                    ):
                        raise DomainError(
                            "Changing an agreed obligation requires a separate scope quote"
                        )
            available = {
                source_pin(self.store.artifact(db, record.id, identifier)[0])
                for identifier in record.source_artifact_ids
            }
            if set(new.sources) - available or {s.source_id for s in new.sources} != {
                s.source_id for s in old.sources
            }:
                raise DomainError(
                    "Clarification may use only supplied revisions "
                    "of the originally accepted sources"
                )
            amendment = BrokerAmendment(
                id=uid("amendment"),
                specification=new,
                effective_at=request.effective_at,
                digest=digest(
                    {
                        "specification": new.model_dump(mode="json"),
                        "effective_at": request.effective_at.isoformat(),
                    }
                ),
            )
            record.amendments.append(amendment)
        else:
            amendment = next(
                (item for item in record.amendments if item.id == request.amendment_id), None
            )
            if amendment is None or request.digest != amendment.digest:
                raise DomainError("Amendment acceptance must bind the exact proposed terms")
            if any(item.amendment_id == amendment.id for item in base.data_amendments):
                raise DomainError("Amendment is already accepted")
            if any(
                item.specification.version >= amendment.specification.version
                for item in base.data_amendments
            ):
                raise DomainError("A newer accepted amendment superseded this proposal")
            if actor.role == "customer":
                amendment.customer_accepted_by = actor.id
            else:
                amendment.provider_accepted_by = actor.id
            if amendment.customer_accepted_by and amendment.provider_accepted_by:
                base.data_amendments = (
                    *base.data_amendments,
                    AcceptedDataAmendment(
                        amendment_id=amendment.id,
                        effective_at=amendment.effective_at,
                        specification=amendment.specification,
                        accepted_by_customer=amendment.customer_accepted_by,
                        accepted_by_provider=amendment.provider_accepted_by,
                    ),
                )
                base.scope_obligations = (
                    *base.scope_obligations,
                    ScopeObligation(
                        amendment_id=amendment.id,
                        effective_at=amendment.effective_at,
                        fields=tuple(r.id for r in amendment.specification.requirements),
                    ),
                )
                self.base._new_binding(base)
                base.revision += 1
                self.base.repository.save(db, base)
                self._emit(
                    db,
                    record,
                    actor,
                    request.idempotency_key,
                    "spec.amendment_accepted",
                    amendment_id=amendment.id,
                    effective_at=amendment.effective_at.isoformat(),
                )
        return base

    def events(self, actor, entity_id, after=0):
        self.draft(actor, entity_id)
        with self.store.connect() as db:
            return storage.events(db, entity_id, after)

    def artifact(self, actor, entity_id, artifact_id):
        self.draft(actor, entity_id)
        with self.store.connect() as db:
            return self.store.artifact(db, entity_id, artifact_id)

    def orders(self, actor):
        with self.store.connect() as db:
            records = [
                BrokerRecord.model_validate_json(row[0])
                for row in db.execute("SELECT body FROM br_orders")
            ]
        return [
            self.view(actor, record.id)
            for record in records
            if actor.role != "customer" or record.customer_id == actor.customer_id
        ]

    def expire_due(self):
        with self.store.connect(write=True) as db:
            for row in db.execute("SELECT body FROM br_orders").fetchall():
                record = BrokerRecord.model_validate_json(row[0])
                self._sync(db, record)
                if record.model_dump_json() != row[0]:
                    storage.save(db, "br_orders", record)
