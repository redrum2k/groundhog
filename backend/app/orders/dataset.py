"""Dataset-specific hooks on the existing CatalogService lifecycle and durable jobs."""

import re

from app.contracts.catalog import Complaint, FulfillmentContext
from app.contracts.dataset import DatasetComplaintTarget
from app.datasets import is_dataset, produce_dataset, verify_dataset
from app.investigation.dataset import (
    guarded_dataset_assessment,
    scope_inquiry,
    semantic_attempt,
    stale_semantic_attempt,
    unclear,
)
from app.orders.service import DomainError


class DatasetLifecycle:
    def dataset_complaint_from_text(self, order, text):
        """Route a customer's words, not their verdict or consent, to a frozen target.

        Ambiguous/multi-topic text targets the whole artifact. Investigation still
        receives the complete complaint and independently verifies every requirement.
        No phrase here authorizes changed scope, fees, correction or settlement.
        """
        patterns = {
            "category": r"\b(?:yoga|fitness|gym|membership|category|taxonomy)\b",
            "cohort": r"\b(?:age|aged|ages|cohort)\b|\b\d{2}\s*[-–]\s*\d{2}\b",
            "geography": r"\b(?:oakland|san francisco|sf|city|geography|boundary)\b",
            "coverage": r"\b(?:duplicate|coverage|completeness)\b",
            "suppression": r"\b(?:suppressed|suppression|privacy|threshold)\b",
            "schema": r"\b(?:schema|columns?|headers?|format)\b",
            "provenance": r"\b(?:provenance|authority|edition|version|authenticity|hash)\b",
        }
        matched = [field for field, pattern in patterns.items() if re.search(pattern, text, re.I)]
        if (
            re.search(r"\b(?:zip|rows?|\d{5})\b", text, re.I)
            and re.search(r"\b(?:missing|omitted)\b", text, re.I)
            and "coverage" not in matched
        ):
            matched.append("coverage")
        field = matched[0] if len(matched) == 1 else "artifact"
        targets = self.complaint_targets(order)
        target = next(t for t in targets if t.field == field)
        mentioned = set(re.findall(r"\b\d{5}\b", text))
        row = next(iter(mentioned)) if len(mentioned) == 1 and len(matched) <= 1 else "dataset"
        if row not in target.row_ids:
            row = "dataset"
        return Complaint(
            text=text,
            product_id=row,
            field=target.field,
            requirement_id=target.requirement_id,
            artifact_id=order.deliveries[-1].csv.artifact_id,
            intent="dispute_fact",
        )

    def reclaim_dataset_assessment(self, db, order):
        """Carry completed work across only the claim's own +1 revision, atomically."""
        if not order.cases or order.cases[-1].status != "open":
            return
        # The key includes the exact case/complaint/answers, accepted specification
        # and evidence binding. An intervening revision is not a pure lease reclaim.
        attempt = semantic_attempt(db, order)
        if (
            attempt
            and attempt.effective is not None
            and attempt.status not in {"DISPATCHED", "STALE"}
            and attempt.binding == order.binding
            and attempt.application_revision == order.revision
            and self.clock() < order.cases[-1].deadline
        ):
            self.repository.put(
                db,
                "dataset_assessment",
                attempt.attempt_id,
                attempt.model_copy(
                    update={"recovery_revisions": (*attempt.recovery_revisions, order.revision + 1)}
                ),
            )

    def complaint_targets(self, order):
        if not order.deliveries:
            return ()
        # Complaints must remain possible when the delivery bytes themselves are unavailable.
        specification = order.snapshot.quote.specification
        rows = tuple(dict.fromkeys(("dataset", *specification.terms.coverage.expected_keys)))
        columns = {
            "coverage": ("zip", "count", "status"),
            "suppression": ("count", "status"),
            "schema": ("zip", "area", "count", "status"),
            "artifact": ("zip", "area", "count", "status"),
        }
        return tuple(
            DatasetComplaintTarget(
                requirement_id=requirement.requirement_id,
                field=requirement.check,
                row_ids=rows if requirement.check in columns else ("dataset",),
                columns=columns.get(requirement.check, ()),
            )
            for requirement in specification.requirements
        )

    def validate_dataset_complaint(self, order, complaint):
        target = next(
            (
                t
                for t in self.complaint_targets(order)
                if t.requirement_id == complaint.requirement_id
            ),
            None,
        )
        if (
            target is None
            or complaint.field != target.field
            or complaint.product_id not in target.row_ids
            or complaint.column is not None
            and (complaint.product_id == "dataset" or complaint.column not in target.columns)
        ):
            raise ValueError(
                "complaint requirement, field, row and column must match an accepted target"
            )

    def current_dataset_checks(self, order):
        if not is_dataset(order):
            return True
        if not order.deliveries:
            return False
        delivery = order.deliveries[-1]
        try:
            report, _ = verify_dataset(
                FulfillmentContext(
                    snapshot=order.snapshot, binding=order.binding, sources=order.sources
                ),
                self.store,
                self.clock(),
                delivery=delivery.csv,
                preview=delivery.preview,
                stage="delivery",
            )
            return report.passed and not report.provider_defect and not report.material_blockers
        except Exception:
            return False

    def run_dataset(self, order, job):
        order_id = order.snapshot.order_id
        try:
            context = FulfillmentContext(
                snapshot=order.snapshot, binding=order.binding, sources=order.sources
            )
            report, _ = verify_dataset(context, self.store, self.clock())
            artifact = preview = None
            if report.passed:
                if job.kind == "reverify" and order.deliveries:
                    artifact = order.deliveries[-1].csv
                    report, _ = verify_dataset(
                        context,
                        self.store,
                        self.clock(),
                        delivery=artifact,
                        preview=order.deliveries[-1].preview,
                        stage="dispute" if order.cases else "delivery",
                    )
                else:
                    artifact, preview = produce_dataset(
                        order.snapshot.quote.specification.terms, order.sources, self.store
                    )
                    context = context.model_copy(
                        update={
                            "binding": order.binding.model_copy(
                                update={"delivery_version": len(order.deliveries) + 1}
                            )
                        }
                    )
                    report, _ = verify_dataset(
                        context,
                        self.store,
                        self.clock(),
                        delivery=artifact,
                        preview=preview,
                        stage="delivery",
                    )
            semantic = None
            if (
                order.cases
                and order.cases[-1].status == "open"
                and report.passed
                and order.cases[-1].complaint.intent != "change_scope"
            ):
                semantic = guarded_dataset_assessment(self, order, job, report)
            return self.complete_verification(order_id, job, report, artifact, preview, semantic)
        except DomainError:
            if order.cases:
                stale_semantic_attempt(self, order)
            raise
        except Exception as exc:
            # Validation errors can contain input rows. Never publish their raw text.
            return self.fail_job(
                order_id,
                job,
                f"Dataset operation failed ({type(exc).__name__}); retained for review.",
            )

    def resolve_dataset_complaint(self, db, order, semantic):
        case = order.cases[-1]
        attempt = semantic_attempt(db, order)
        if attempt and (
            attempt.binding != order.binding
            or attempt.application_revision != order.revision
            or attempt.status == "STALE"
            or self.clock() >= case.deadline
        ):
            semantic = unclear(
                order, "Assessment binding or case deadline is stale; retained for review."
            )
            attempt = attempt.model_copy(update={"status": "STALE", "effective": semantic})
            self.repository.put(db, "dataset_assessment", attempt.attempt_id, attempt)
        evidence_ids = []
        if semantic:
            for ref in (*semantic.citations, *semantic.conflicting_evidence):
                self.store.resolve(ref, order.artifacts)
            order.semantic_findings = (*order.semantic_findings, semantic)
            for i, ref in enumerate((*semantic.citations, *semantic.conflicting_evidence)):
                evidence_id = f"{case.case_id}:semantic:{order.binding.evidence_revision}:{i}"
                evidence_ids.append(evidence_id)
                self.effects.emit(
                    db,
                    order,
                    evidence_id,
                    type="evidence_found",
                    step="investigate",
                    evidence={
                        "id": evidence_id,
                        "kind": "sheet_cell",
                        "file": ref.artifact_id,
                        "label": f"{ref.source_id} · {ref.column}",
                        "note": semantic.explanation,
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
        if case.complaint.intent == "change_scope":
            # No extra purchase consent, no alteration of the accepted base agreement.
            updated = case.model_copy(update={"status": "unsupported"})
            reason = (
                "Requested additional scope is not owed. A separate provider "
                "offer, explicit acceptance and funding are required; no "
                "complaint fee."
            )
            kind = "disagree"
        elif semantic and semantic.result in {"PASS", "FAIL"} and scope_inquiry(case.complaint):
            # Answered contract questions are neither breaches nor purchases.
            # All original review, acceptance and payment gates still apply.
            updated = case.model_copy(update={"status": "answered", "question": None})
            reason, kind = (
                semantic.explanation,
                "disagree" if semantic.result == "FAIL" else "agree",
            )
        elif semantic and semantic.result == "FAIL":
            updated = case.model_copy(update={"status": "unsupported"})
            reason, kind = semantic.explanation, "disagree"
        elif semantic and semantic.result == "PASS":
            # A source interpretation is a finding, not independent proof of a defective output.
            self._human(
                order,
                (
                    "Cited interpretation supports the complaint; establish the "
                    "actual provider defect before any free correction."
                ),
            )
            updated = order.cases[-1]
            reason, kind = semantic.explanation, "grey"
        elif (
            case.questions_asked < order.snapshot.quote.policy.max_questions
            and self.clock() < case.deadline
        ):
            question = (
                semantic.requested_evidence
                if semantic and semantic.requested_evidence
                else (
                    "Identify the frozen source and exact cell establishing the "
                    "disputed requirement."
                )
            )
            updated = case.model_copy(
                update={"questions_asked": case.questions_asked + 1, "question": question}
            )
            reason, kind = (
                "A bounded evidence question is pending; payment remains blocked.",
                "grey",
            )
            self.effects.message(
                db,
                order.snapshot.quote.request_id,
                f"{case.case_id}:question:{updated.questions_asked}",
                question,
                step="investigate",
            )
            self.effects.emit(
                db,
                order,
                f"{case.case_id}:wait:{updated.questions_asked}",
                type="step_waiting",
                step="investigate",
                waitingOn="Actual buyer evidence answer",
            )
        else:
            self._human(
                order, "Unresolved after bounded investigation; Human must review the evidence."
            )
            updated = order.cases[-1]
            reason, kind = order.error, "grey"
        order.cases = (*order.cases[:-1], updated)
        order.error = reason
        finding = None
        decided_by = "rules"
        if attempt and semantic:
            from app.orders.run_events import binding

            decided_by = (
                "model"
                if attempt.status == "VALIDATED" and semantic.provenance.kind == "model"
                else "rules"
                if semantic.result in {"PASS", "FAIL"}
                else "unresolved"
            )
            finding = dict(
                kind={"PASS": "supported", "FAIL": "contradicted"}.get(semantic.result, "unclear"),
                reason=semantic.explanation,
                evidence_ids=evidence_ids,
                decided_by=decided_by,
                binding=binding(order)
                .model_copy(update={"revision": order.revision + 1})
                .model_dump(),
                assessed_binding=attempt.binding.model_dump(),
                accepted_specification_sha256=attempt.accepted_specification_sha256,
                attempt_id=attempt.attempt_id,
                reviewer_guidance=(attempt.request or {}).get("reviewer_guidance", []),
                candidate=attempt.candidate.model_dump() if attempt.candidate else None,
                effective=semantic.model_dump(),
                validation=attempt.status,
            )
        self.effects.emit(
            db,
            order,
            f"{case.case_id}:verdict:{order.binding.evidence_revision}",
            type="verdict",
            step="verdict",
            verdict={
                "kind": kind,
                "reason": reason,
                "decidedBy": decided_by,
                "evidenceIds": evidence_ids,
                "finding": finding,
            },
            allowedBy=(
                "Frozen accepted definition and resolving source evidence; this "
                "finding grants no payment permission"
            ),
        )
        # The existing Customer and Finding views render persisted messages.
        # Publish only the effective finding, never promote a rejected candidate.
        result = semantic.result if semantic else "Not assessed (scope request)"
        explanation = semantic.explanation if semantic else reason
        assessor = (
            f"Assessor: {semantic.provenance.assessor} ({semantic.provenance.version}).\n"
            if semantic
            else ""
        )
        self.effects.message(
            db,
            order.snapshot.quote.request_id,
            f"{case.case_id}:finding-message:{order.binding.evidence_revision}",
            f"Buyer complaint: {case.complaint.text}\n"
            f"Finding: {result}. Provenance: {decided_by}.\n"
            f"{assessor}{explanation}\nThis finding does not authorize payment.",
            step="verdict",
            attach=[{"kind": "evidence", "evidenceId": item} for item in evidence_ids],
        )
        self.effects.emit(
            db,
            order,
            f"{case.case_id}:finding-complete:{order.binding.evidence_revision}",
            type="step_completed",
            step="verdict",
        )
        if updated.status != "open" or not updated.question:
            self.effects.emit(
                db,
                order,
                f"{case.case_id}:investigation-complete:{order.binding.evidence_revision}",
                type="step_completed",
                step="investigate",
            )
