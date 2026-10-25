"""Translate explicit committed lifecycle effects into Lucas's typed canvas vocabulary."""

from app.contracts.dataset import DatasetManifest, DatasetReference
from app.contracts.runs import DecisionBinding
from app.datasets import is_dataset
from app.storage.runs import RunEvents

MAIN_STEPS = [
    {"id": key, "kind": key, "title": title, "detail": detail, "panel": True}
    for key, title, detail in (
        ("clarify", "Clarify", "Agree on the cohort, sources and price"),
        ("paid", "Funds held", "Buyer authorization and confirmed funding"),
        ("produce", "Produce & check", "Validate CSV and preview against the contract"),
        ("review", "Customer review", "Accepted server review window"),
        ("captured", "Captured", "Confirmed settlement and recorded booking"),
    )
]
DISPUTE_STEPS = [
    {"id": key, "kind": key, "title": title, "detail": detail, "panel": True}
    for key, title, detail in (
        ("investigate", "Investigate", "Resolve the complaint against cited evidence"),
        ("verdict", "Finding", "Evidence assessment; no payment authority"),
        ("decide", "Human reviews", "Bounded reviewer actions on current evidence"),
    )
]


def binding(order):
    return DecisionBinding(
        runId=order.snapshot.quote.request_id,
        orderId=order.snapshot.order_id,
        snapshotId=order.binding.snapshot_id,
        revision=order.revision,
        deliveryVersion=order.binding.delivery_version,
        evidenceVersion=order.binding.evidence_revision,
    )


class CanvasEffects:
    def __init__(self, owner):
        self.owner = owner
        self.log = RunEvents(owner.repository)

    def append(self, db, run_id, key, **event):
        return self.log.append(db, run_id, key, self.owner.clock(), **event)

    def emit(self, db, order, key, **event):
        if is_dataset(order):
            return self.append(db, order.snapshot.quote.request_id, key, **event)

    def message(self, db, run_id, key, text, *, speaker="agent", step="clarify", **extra):
        return self.append(
            db,
            run_id,
            key,
            type="message",
            step=step,
            message={"id": key, "from": speaker, "text": text, **extra},
        )

    def created(self, db, draft):
        db.execute("INSERT INTO runs VALUES(?,NULL)", (draft.request_id,))
        self.append(db, draft.request_id, "plan", type="steps_planned", steps=MAIN_STEPS)
        self.append(db, draft.request_id, "intake", type="step_started", step="clarify")
        self.message(db, draft.request_id, "buyer:intake", draft.prompt, speaker="buyer")

    def compiled(self, db, draft):
        if draft.error:
            self.message(db, draft.request_id, f"draft-error:{draft.revision}", draft.error)
            self.append(
                db,
                draft.request_id,
                f"draft-stopped:{draft.revision}",
                type="step_waiting",
                step="clarify",
                waitingOn="Human review",
            )
            return
        if draft.question:
            self.message(
                db,
                draft.request_id,
                draft.question.question_id,
                draft.question.prompt,
                asks=draft.question.field,
            )
            self.append(
                db,
                draft.request_id,
                f"question:{draft.revision}",
                type="step_waiting",
                step="clarify",
                waitingOn="AcmeFitness's answer",
            )
        if draft.specification:
            for r in draft.specification.requirements:
                self.append(
                    db,
                    draft.request_id,
                    f"draft:{draft.revision}:{r.requirement_id}",
                    type="contract_line_drafted",
                    step="clarify",
                    line={"id": r.requirement_id, "text": r.wording, "check": "code"},
                )

    def quoted(self, db, quote):
        self.message(
            db,
            quote.request_id,
            quote.quote_id,
            f"Provider offers: {quote.work_description} Price ${quote.amount.amount_minor // 100}. "
            "Explicit buyer acceptance is required.",
        )

    def accepted(self, db, order):
        quote = order.snapshot.quote
        db.execute(
            "UPDATE runs SET order_id=? WHERE id=?", (order.snapshot.order_id, quote.request_id)
        )
        self.emit(
            db,
            order,
            "accepted",
            type="contract_approved",
            step="clarify",
            contract={
                "version": 1,
                "buyer": "AcmeFitness",
                "title": quote.specification.summary,
                "price": quote.amount.amount_minor // 100,
                "lines": [
                    {"id": r.requirement_id, "text": r.wording, "check": "code"}
                    for r in quote.specification.requirements
                ],
            },
            allowedBy="Buyer explicitly accepted the identified server quote and frozen terms.",
        )
        if quote.purpose != "initial":
            self.emit(
                db,
                order,
                "accepted-child",
                type="amendment_signed",
                step="clarify",
                amendment={
                    "id": quote.quote_id,
                    "summary": quote.work_description,
                    "price": quote.amount.amount_minor // 100,
                    "line": {"id": quote.quote_id, "text": quote.work_description, "check": "code"},
                },
                allowedBy=(
                    "Durable buyer acceptance of this separate quote; funding remains separate."
                ),
            )
        self.emit(db, order, "clarify:complete", type="step_completed", step="clarify")
        self.emit(db, order, "funding:start", type="step_started", step="paid")
        self.emit(
            db,
            order,
            "funding:waiting",
            type="step_waiting",
            step="paid",
            waitingOn="Buyer funding authorization; acceptance alone does not fund work",
        )

    def state(self, db, order):
        if not is_dataset(order):
            return
        payment = self.owner.payments.view(db, order)
        if payment:
            self.emit(
                db,
                order,
                f"payment-state:{order.revision}",
                type="payment_state_changed",
                payment={
                    "id": order.payment_id,
                    "amount": order.snapshot.quote.amount.amount_minor // 100,
                    "mock": payment.simulated,
                },
                state=payment.payment.state,
                reason=payment.payment.last_error,
            )
        self.emit(
            db,
            order,
            f"order:{order.revision}",
            type="state_changed",
            step="paid" if order.order_state == "awaiting_authorization" else "review",
            state=order.order_state,
            reason=order.error,
            binding=binding(order).model_dump(),
            paymentState=payment.payment.state if payment else None,
        )
        if order.order_state == "human_review":
            self.emit(db, order, "dispute-plan", type="steps_planned", steps=DISPUTE_STEPS)
            self.emit(
                db,
                order,
                f"reviewer:{order.revision}",
                type="step_waiting",
                step="decide",
                waitingOn=order.error or "Human's review",
            )

    def job(self, db, order, job):
        self.emit(
            db,
            order,
            f"job:{job.job_id}:attempt:{job.attempts}",
            type="step_started",
            step="investigate" if job.kind == "reverify" and order.cases else "produce",
            attempt=1 + order.free_corrections_used,
        )

    def verified(self, db, order, job, report, published=False):
        if not is_dataset(order):
            return
        attempt = 2 if job.kind == "correct" else max(1, len(order.deliveries))
        for assessment in report.assessments:
            passed = assessment.result == "PASS"
            kwargs = (
                {"detail": assessment.explanation}
                if passed
                else {"reason": assessment.explanation, "assessment": assessment.result}
            )
            self.emit(
                db,
                order,
                f"check:{job.job_id}:{job.attempts}:{assessment.obligation_id}",
                type="check_passed" if passed else "check_failed",
                step="produce",
                attempt=attempt,
                lineId="R-" + assessment.obligation_id.split(":")[-1].upper(),
                **kwargs,
            )
            for i, ref in enumerate(assessment.citations):
                if not isinstance(ref, DatasetReference):
                    continue
                self.owner.store.resolve(ref, order.artifacts)
                evidence_id = f"{job.job_id}:{assessment.obligation_id}:{i}"
                self.emit(
                    db,
                    order,
                    f"evidence:{evidence_id}",
                    type="evidence_found",
                    step="investigate" if order.cases else "produce",
                    attempt=attempt,
                    evidence={
                        "id": evidence_id,
                        "label": f"{ref.source_id} · {ref.row} · {ref.column}",
                        "note": assessment.explanation,
                        "kind": "sheet_cell",
                        "file": ref.artifact_id,
                        "row": ref.row,
                        "column": ref.column,
                        "value": ref.value,
                        "source": {
                            "kind": "cell",
                            "version": ref.version,
                            "row": ref.row,
                            "column": ref.column,
                            "reference": ref.model_dump(),
                        },
                    },
                )
        if published:
            delivery = order.deliveries[-1]
            manifest = DatasetManifest.model_validate_json(self.owner.store.read(delivery.preview))
            self.emit(
                db,
                order,
                f"delivery:{delivery.version}",
                type="delivery_ready",
                step="review",
                attempt=delivery.version,
                delivery={
                    "version": delivery.version,
                    "file": f"dataset-v{delivery.version}.csv",
                    "rows": [
                        {**r.model_dump(), "flag": "withheld" if r.status == "suppressed" else None}
                        for r in manifest.rows
                    ],
                    "reviewClosesAt": delivery.review_deadline.isoformat(),
                    "artifactId": delivery.csv.artifact_id,
                    "sha256": delivery.csv.sha256,
                    "previewArtifactId": delivery.preview.artifact_id,
                },
            )
            self.emit(
                db,
                order,
                f"produced:{delivery.version}",
                type="step_completed",
                step="produce",
                attempt=delivery.version,
            )
            self.emit(
                db,
                order,
                f"review:{delivery.version}",
                type="step_started",
                step="review",
                attempt=delivery.version,
            )

    def disputed(self, db, order):
        case = order.cases[-1]
        self.emit(db, order, "dispute-plan", type="steps_planned", steps=DISPUTE_STEPS)
        self.emit(
            db,
            order,
            case.case_id,
            type="dispute_opened",
            step="investigate",
            dispute={"id": case.case_id, "claim": case.complaint.text, "raisedBy": "AcmeFitness"},
        )
        self.message(
            db,
            order.snapshot.quote.request_id,
            f"{case.case_id}:buyer-complaint",
            case.complaint.text,
            speaker="buyer",
            step="investigate",
        )

    def payment(self, db, order, action, receipt):
        if action == "fund":
            self.emit(
                db,
                order,
                f"funded:{order.payment_id}",
                type="payment_authorized",
                payment={
                    "id": order.payment_id,
                    "amount": order.snapshot.quote.amount.amount_minor // 100,
                    "mock": receipt.mode == "mock",
                },
                allowedBy="Confirmed held funding"
                if receipt.mode != "mock"
                else "Explicit simulated funding; no chain transaction",
            )
            self.emit(db, order, "paid:complete", type="step_completed", step="paid")
        elif action == "capture":
            if order.order_state == "closed":
                self.emit(db, order, "review:complete", type="step_completed", step="review")
            self.emit(
                db,
                order,
                f"capture:{receipt.operation_id}",
                type="payment_captured",
                paymentId=order.payment_id,
                captureTx=receipt.transaction_id if receipt.mode == "live" else None,
                allowedBy=(
                    "Current mandatory checks, review trigger and exact payment "
                    "authority; completed payment evidence"
                ),
            )
            self.emit(
                db,
                order,
                f"books:{receipt.operation_id}",
                type="books_posted",
                step="captured",
                entries=[],
                operationIds=[b.operation_id for b in order.ledger],
                margin=None,
                note=(
                    "Existing idempotent capture booking. Cost/margin unavailable; no "
                    "double-entry or external accounting integration claimed."
                ),
            )
            self.emit(db, order, "capture:complete", type="step_completed", step="captured")
