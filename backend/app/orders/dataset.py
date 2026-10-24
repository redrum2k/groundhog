"""Dataset-specific hooks on the existing CatalogService lifecycle and durable jobs."""

from app.contracts.catalog import FulfillmentContext
from app.contracts.dataset import DATASET_CHECKS, DatasetComplaintTarget, DatasetManifest
from app.datasets import is_dataset, produce_dataset, verify_dataset
from app.investigation.dataset import investigate_dataset
from app.orders.service import DomainError


class DatasetLifecycle:
    def complaint_targets(self, order):
        if not order.deliveries:
            return ()
        delivery = order.deliveries[-1]
        manifest = DatasetManifest.model_validate_json(self.store.read(delivery.preview))
        rows = tuple(
            dict.fromkeys(
                (
                    "dataset",
                    *order.snapshot.quote.specification.terms.coverage.expected_keys,
                    *(r.zip for r in manifest.rows),
                )
            )
        )
        columns = {
            "coverage": ("zip", "count", "status"),
            "suppression": ("count", "status"),
            "schema": ("zip", "area", "count", "status"),
            "artifact": ("zip", "area", "count", "status"),
        }
        return tuple(
            DatasetComplaintTarget(
                requirement_id=f"R-{field.upper()}",
                field=field,
                row_ids=rows if field in columns else ("dataset",),
                columns=columns.get(field, ()),
            )
            for field in DATASET_CHECKS
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
                semantic = investigate_dataset(
                    order, report, self.store, self.investigator.assessor
                )
            return self.complete_verification(order_id, job, report, artifact, preview, semantic)
        except DomainError:
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
                order, "Unresolved after bounded investigation; Maya must review the evidence."
            )
            updated = order.cases[-1]
            reason, kind = order.error, "grey"
        order.cases = (*order.cases[:-1], updated)
        order.error = reason
        self.effects.emit(
            db,
            order,
            f"{case.case_id}:verdict:{order.binding.evidence_revision}",
            type="verdict",
            step="verdict",
            verdict={
                "kind": kind,
                "reason": reason,
                "decidedBy": "rules",
                "evidenceIds": evidence_ids,
            },
            allowedBy=(
                "Frozen accepted definition and resolving source evidence; this "
                "finding grants no payment permission"
            ),
        )
