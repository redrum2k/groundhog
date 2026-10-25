"""Drive existing application commands; no expected outcomes are accepted here."""

import json
import os
import time
from contextlib import nullcontext
from unittest.mock import patch

from evals.aggregate.execution import offline_guards
from evals.roi.ledger import Ledger
from evals.roi.plan import ROOT, digest, save
from tools.brokerage_acceptance import Clock, accept, cmd, fund

from app.agents.source_preparation import compile_composed_sources
from app.contracts.catalog import Complaint, DisputeCommand, QuoteRequest, RevisionCommand
from app.contracts.runs import RunCreate, RunOffer
from app.contracts.source_learning import BundleUpload, LearningCommand, ResolveSource
from app.datasets import produce_dataset
from app.learning.service import OWNER, SourceLearning
from app.orders.catalog import CatalogService
from app.orders.payment_justification import payment_justification
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.storage.catalog import CatalogRepository


class Arm:
    def __init__(self, root, name):
        self.root, self.name = root, name
        self.service = CatalogService(
            CatalogRepository(root / "orders.sqlite3"), root / "artifacts", Clock()
        )
        self.learning = SourceLearning(self.service, enabled=True)
        self.service.source_learning = self.learning
        self.notes_path = root / "operator-glossary.json"
        self.notes = json.loads(self.notes_path.read_text()) if self.notes_path.exists() else []
        self.owner = {
            r["source_family"]: r
            for r in json.loads((ROOT / "docs/examples/judge-owner-walkthroughs.json").read_text())[
                "walkthroughs"
            ]
        }

    def compile(self, request, key):
        draft = self.service.get_request(request)
        return self.service.compile_request(
            request, RevisionCommand(expected_revision=draft.revision, idempotency_key=key)
        )

    def intake(self, case, ledger):
        s, learning = self.service, self.learning
        bundle = learning.publish(
            BundleUpload.model_validate(case["source"]), "provider:roi-synthetic-source"
        )
        request = (
            Runs(s)
            .create(RunCreate(prompt=case["prompt"], corpus_id="sf-aggregate-v1"), case["case_id"])
            .id
        )
        if self.name == "operator":
            # The comparator may apply its own previously recorded glossary with the
            # SAME source-currentness checks and normalizer. This is a manual tool
            # invocation, not an activated autonomous procedure or a memoryless human.
            engine = learning.engine(tuple(self.notes))
            assessments = [engine.assess(c) for c in learning.cases(request, learning.bundle())]
            ledger.add(
                "operator",
                "glossary_lookup_apply",
                request,
                source="scripted_operator_tool_invocation",
            )
            if all(not r["internal_reviews"] for r in assessments):
                draft = compile_composed_sources(
                    engine,
                    tuple(r["encounter_id"] for r in assessments),
                    idempotency_key=request + ":manual-compile",
                )
            else:
                draft = self.compile(request, request + ":compile")
        else:
            draft = self.compile(request, request + ":compile")
        initial_reviews = [
            r for r in learning.state().reviews if r.request_id == request and not r.resolved
        ]
        # A new owner explanation is supplied only for genuine source ambiguity.
        # Revocation, conflicts and changed schemas/epochs are not silently undone.
        if case["source_mode"] in ("normal", "documented"):
            for review in initial_reviews:
                if not review.actionable:
                    continue
                explanation = self.owner[review.source_family]
                result = learning.resolve(
                    ResolveSource(
                        idempotency_key=request + ":owner:" + review.source_family,
                        encounter_id=review.encounter_id,
                        column=explanation["column"],
                        explanation=explanation["explanation"],
                    ),
                    OWNER,
                )
                ledger.add("source_owner", "source_explanation", result.record_id)
                ledger.add("operator", "source_coordination", result.record_id)
                if self.name == "operator":
                    self.notes.append(result.record_id)
            if initial_reviews:
                draft = self.compile(request, request + ":after-owner")
        if self.name == "operator" and not self.notes_path.exists() and self.notes:
            save(self.notes_path, self.notes)
        ledger.add("operator", "routine_oversight", request, source="declared_scripted_oversight")
        if (
            case["phase"] == "setup"
            and self.name == "approved_learning"
            and draft.status == "ready"
        ):
            candidate = learning.propose(
                LearningCommand(idempotency_key=request + ":propose", target_id=bundle.record_id),
                "provider:roi",
            )
            qualification = learning.qualify(
                LearningCommand(
                    idempotency_key=request + ":qualify", target_id=candidate.record_id
                ),
                "controller:roi",
            )
            ledger.add("controller", "qualification_review", qualification.record_id)
            approved = learning.transition(
                LearningCommand(
                    idempotency_key=request + ":approve", target_id=candidate.record_id
                ),
                "controller:roi",
                "approve",
            )
            ledger.add("controller", "procedure_approval", approved.record_id)
            learning.transition(
                LearningCommand(
                    idempotency_key=request + ":activate", target_id=approved.record_id
                ),
                "controller:roi",
                "activate",
            )
            ledger.add("controller", "activation_check", approved.record_id)
        return draft, request, len(initial_reviews)

    def quote_fund(self, draft, ledger, *, quote=None):
        s = self.service
        quote = quote or s.issue_quote(
            draft.request_id,
            QuoteRequest(
                expected_revision=draft.revision, idempotency_key=draft.request_id + ":quote"
            ),
        )
        order = accept(s, quote, quote.quote_id + ":buyer-accept")
        ledger.add("buyer", "contract_consent", quote.quote_id, order_id=order.snapshot.order_id)
        assert order.authorization.status == "pending" and not order.deliveries
        order = fund(s, order)
        ledger.add("buyer", "funding_consent", quote.quote_id, order_id=order.snapshot.order_id)
        return order

    def capture(self, order, ledger):
        s = self.service
        # Explicit scripted final check and acceptance. No accelerated expiry is
        # counted as labor, and no verdict alone is used as collection authority.
        ledger.add(
            "operator",
            "final_review",
            order.deliveries[-1].csv.artifact_id,
            source="scripted_operator_inspection",
            order_id=order.snapshot.order_id,
        )
        command = cmd(order, "delivery-accepted")
        result = s.mutate(order.snapshot.order_id, "accept", command)
        replay = s.mutate(order.snapshot.order_id, "accept", command)
        assert replay == result
        ledger.add(
            "buyer",
            "delivery_acceptance",
            order.snapshot.order_id,
            order_id=order.snapshot.order_id,
        )
        return result

    def complaint(self, order, case, ledger):
        s = self.service
        order = s.mutate(
            order.snapshot.order_id,
            "dispute",
            DisputeCommand(
                **cmd(order, "complaint").model_dump(),
                complaint=Complaint(
                    artifact_id=order.deliveries[-1].csv.artifact_id,
                    requirement_id="R-COVERAGE"
                    if case["complaint_field"] == "coverage"
                    else "R-CATEGORY",
                    product_id=case["target"],
                    field=case["complaint_field"],
                    text=case["complaint"],
                    intent="dispute_fact",
                ),
            ),
        )
        ledger.add(
            "buyer",
            "objection_submission",
            order.cases[-1].case_id,
            order_id=order.snapshot.order_id,
        )
        order = s.run_one(order.snapshot.order_id)
        ledger.add(
            "operator",
            "finding_review",
            order.cases[-1].case_id,
            source="scripted_operator_inspection",
            order_id=order.snapshot.order_id,
        )
        return order

    def run(self, case):
        started = time.monotonic()
        case_root = self.root / "cases" / case["case_id"]
        case_root.mkdir(parents=True, exist_ok=False)
        ledger = Ledger(case, self.name, digest(case))
        outcome = dict(
            case_id=case["case_id"],
            stream_id=case["stream_id"],
            category=case["category"],
            phase=case["phase"],
            arm=self.name,
            input_hash=digest(case),
            source_hashes=[digest(p) for p in case["source"]["partitions"]],
            orders=[],
            error=None,
            process_id=os.getpid(),
            initial_source_reviews=0,
            configured_procedure=None,
            reused_procedure=None,
            source_mode=case["source_mode"],
            provider_calls=0,
            provider_cost_usd=0,
            compute_cost_usd=None,
            timing_mode="deterministic_clock_not_throughput",
            human_attention_seconds=None,
            emitted_events=0,
        )
        try:
            draft, request, reviews = self.intake(case, ledger)
            outcome.update(request_id=request, initial_source_reviews=reviews)
            active = self.learning.active()
            outcome["configured_procedure"] = active["id"] if active else None
            attempts = [a for a in self.learning.state().attempts if a.request_id == request]
            outcome["reused_procedure"] = attempts[-1].active_version if attempts else None
            if draft.status != "ready":
                outcome["observed_disposition"] = "held_before_acceptance"
                ledger.add(
                    "operator", "exception_review", request, source="scripted_operator_inspection"
                )
            else:
                calls = []

                def inject_missing_zip(terms, sources, store):
                    csv, preview = produce_dataset(terms, sources, store)
                    calls.append(1)
                    if len(calls) == 1:
                        raw = (
                            b"\n".join(
                                line
                                for line in store.read(csv).splitlines()
                                if not line.startswith(b"94110,")
                            )
                            + b"\n"
                        )
                        csv = store.put(raw, "text/csv")
                    return csv, preview

                with (
                    patch("app.orders.dataset.produce_dataset", inject_missing_zip)
                    if case["action"] == "repair"
                    else nullcontext()
                ):
                    order = self.quote_fund(draft, ledger)
                    if case["action"] == "repair":
                        save(
                            case_root / "detected-output-fault.json", order.model_dump(mode="json")
                        )
                        order = self.service.run_one(order.snapshot.order_id)
                        ledger.add(
                            "operator",
                            "rework_review",
                            order.snapshot.order_id,
                            source="scripted_operator_inspection",
                            order_id=order.snapshot.order_id,
                        )
                parents = []
                if case.get("child_scope"):
                    parent = self.capture(order, ledger)
                    parents.append(parent)
                    offer = Runs(self.service).offer(
                        parent.snapshot.quote.request_id,
                        RunOffer(binding=binding(parent), scope=case["child_scope"]),
                        "separate-offer",
                        "provider:roi",
                    )
                    ledger.add(
                        "operator",
                        "scope_offer_review",
                        offer.quote_id,
                        source="scripted_operator_inspection",
                    )
                    order = self.quote_fund(draft, ledger, quote=offer)
                if case["action"] in ("question", "unavailable"):
                    order = self.complaint(order, case, ledger)
                if case["action"] == "unavailable":
                    ledger.add(
                        "operator",
                        "exception_review",
                        order.cases[-1].case_id,
                        source="scripted_operator_inspection",
                        order_id=order.snapshot.order_id,
                    )
                    outcome["observed_disposition"] = "held_funded"
                elif any(c.status in ("open", "human_review", "scope_change") for c in order.cases):
                    outcome["observed_disposition"] = "unnecessary_escalation"
                    ledger.add(
                        "operator",
                        "unnecessary_escalation",
                        order.cases[-1].case_id,
                        source="scripted_operator_inspection",
                        order_id=order.snapshot.order_id,
                    )
                else:
                    order = self.capture(order, ledger)
                    outcome["observed_disposition"] = "fulfilled"
                for index, saved in enumerate(parents + [order]):
                    oid = saved.snapshot.order_id
                    view = self.service.current_view(oid)
                    record = view.order.model_dump(mode="json")
                    save(case_root / f"order-{index}.json", record)
                    save(
                        case_root / f"justification-{index}.json",
                        payment_justification(self.service, oid).model_dump(mode="json"),
                    )
                    page = Runs(self.service).page(saved.snapshot.quote.request_id)
                    save(
                        case_root / f"events-{index}.json",
                        page.model_dump(mode="json", by_alias=True),
                    )
                    outcome["emitted_events"] += len(page.events)
                    outcome["orders"].append(
                        dict(
                            order_id=oid,
                            record=f"order-{index}.json",
                            justification=f"justification-{index}.json",
                        )
                    )
            save(
                case_root / "request.json",
                self.service.get_request(request).model_dump(mode="json"),
            )
            save(case_root / "learning.json", self.learning.state().model_dump(mode="json"))
            save(
                case_root / "learning-records.json",
                {
                    kind: self.learning.memory.records(kind)
                    for kind in (
                        "source_attempt",
                        "source_encounter",
                        "source_resolution",
                        "source_procedure",
                        "source_version",
                        "source_qualification",
                    )
                },
            )
        except Exception as error:
            outcome.update(
                error=f"{type(error).__name__}: {error}", observed_disposition="execution_failed"
            )
        outcome["machine_elapsed_seconds"] = round(time.monotonic() - started, 6)
        outcome["artifact_directory"] = str(case_root)
        for event in ledger.events.values():
            event["procedure_version"] = outcome["reused_procedure"]
            event["observed_disposition"] = outcome["observed_disposition"]
        save(case_root / "result.json", outcome)
        save(case_root / "work.json", list(ledger.events.values()))
        return outcome


def worker(directory, arm, stream, start, stop):
    plan = json.loads((directory / "inputs.json").read_text(encoding="utf-8"))
    cases = [c for c in plan["setup"] + plan["cases"] if c["stream_id"] == stream][start:stop]
    system_root = os.environ.get("SystemRoot")
    with (
        offline_guards(),
        patch.dict(os.environ, {"SystemRoot": system_root} if system_root else {}),
    ):
        current = Arm(directory / "arms" / arm / stream, arm)
        for case in cases:
            result = current.run(case)
            print(
                json.dumps(
                    {
                        "arm": arm,
                        "case": case["case_id"],
                        "disposition": result["observed_disposition"],
                        "error": result["error"],
                    }
                ),
                flush=True,
            )
