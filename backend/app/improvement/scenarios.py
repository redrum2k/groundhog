"""Dataset seam: ordinary business inputs only. Expected outcomes live with the evaluator."""

import base64
import json
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from app.contracts.broker import BrokerCommand, DraftCreate, IntakeDraft, SourceUpload
from app.contracts.data_product import DataSpecification, Frozen, Name, Parameters
from app.contracts.improvement import ImprovementVersion
from app.contracts.models import Money
from app.data_products import FIELDS, specification_digest
from app.investigation.documents import extract_document
from app.runtime.broker import Broker
from app.runtime.jobflow import DEMO_ACTORS, Jobflow
from app.storage import broker as storage
from app.storage import improvement as improvements
from app.storage.jobflow import digest, uid

FORBIDDEN_KEYS = {
    "gold",
    "expected",
    "expected_verdict",
    "expected_outcome",
    "reference_answer",
    "truth",
    "world_truth",
    "mutation",
    "mutation_label",
    "repair_recipe",
    "test_id",
    "test_name",
    "score",
    "grader",
    "labels",
    "holdout",
}


def assert_visible(value):
    if isinstance(value, dict):
        if {str(key).casefold() for key in value} & FORBIDDEN_KEYS:
            raise ValueError("Protected evaluator metadata is not a product-visible input")
        for item in value.values():
            assert_visible(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_visible(item)
    elif isinstance(value, str) and any(
        marker in value.casefold()
        for marker in (
            "[gold]",
            "expected_verdict",
            "repair_recipe",
            "reference_answer",
            "world_truth",
        )
    ):
        raise ValueError("Protected evaluator annotation found in visible text")


class ScenarioArtifact(Frozen):
    filename: Name
    media_type: Literal["application/json", "application/pdf", "text/csv"]
    content_base64: Annotated[str, Field(min_length=1, max_length=2_800_000)]


class VisibleScenario(Frozen):
    case_id: Annotated[str, Field(pattern=r"^case-[a-f0-9]{12}$")]
    customer_id: Name = "northwind"
    product_id: Name = "aggregate_regional_market_intelligence"
    intent: Annotated[str, Field(min_length=1, max_length=8000)]
    as_of: AwareDatetime
    sources: Annotated[tuple[ScenarioArtifact, ...], Field(min_length=1, max_length=16)]
    customer_answers: dict[str, str | int | list[str]]
    customer_behavior: Literal["truthful", "decline", "evasive"] = "truthful"
    historical_specification: DataSpecification | None = None
    delivered_artifacts: tuple[ScenarioArtifact, ...] = ()
    authorization_seconds: Annotated[int, Field(ge=1, le=86400)] = 3600


class ScenarioManifest(Frozen):
    schema_version: Literal[1] = 1
    cases: Annotated[tuple[VisibleScenario, ...], Field(min_length=1, max_length=64)]


class ScenarioClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class ConstrainedCustomer:
    def __init__(self, scenario):
        self.scenario = scenario

    def answer(self, question):
        if self.scenario.customer_behavior != "truthful":
            return None
        required_words = {
            "freshness_basis": ("observation", "publication", "export"),
            "max_age_days": ("age", "days"),
            "as_of": ("as-of",),
        }
        if not all(
            word in question.prompt.casefold() for word in required_words.get(question.field, ())
        ):
            return None
        return self.scenario.customer_answers.get(question.field)


class ScenarioAdapter:
    @staticmethod
    def load(raw: bytes):
        extraction = extract_document(raw, "scenarios.json", "application/json")
        assert_visible(extraction["structured"])
        manifest = ScenarioManifest.model_validate(extraction["structured"])
        if len({case.case_id for case in manifest.cases}) != len(manifest.cases):
            raise ValueError("Scenario IDs must be unique and neutral")
        for case in manifest.cases:
            if set(case.customer_answers) - set(FIELDS):
                raise ValueError("Customer answer interface contains unsupported fields")
            for artifact in (*case.sources, *case.delivered_artifacts):
                raw_artifact = base64.b64decode(artifact.content_base64, validate=True)
                if artifact.media_type == "application/json":
                    try:
                        assert_visible(json.loads(raw_artifact))
                    except json.JSONDecodeError:
                        pass
        return manifest.cases

    def execute(self, scenario, *, template=None, arm="static", experience_ids=()):
        """Each arm receives an isolated DB, fake authority and actual application commands."""
        if arm not in {"static", "memory_only", "evolving_process"}:
            raise ValueError("Unknown comparison arm")
        started = time.perf_counter()
        actor = {item.id: item for item in DEMO_ACTORS}
        actor["customer"] = actor["customer"].model_copy(
            update={"customer_id": scenario.customer_id}
        )
        trace = []
        violations = []
        result = {
            "case_id": scenario.case_id,
            "arm": arm,
            "outcome": "ERROR",
            "accepted": False,
            "completed": False,
            "company_staff_touches": 0,
            "measured_staff_seconds": None,
            "customer_answers": 0,
            "required_review_tasks": 0,
            "seller_rework_attempts": 0,
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "financial_effects": 0,
            "observed_answer_fidelity": True,
            "experience_ids": list(experience_ids) if arm == "memory_only" else [],
            "violations": violations,
            "artifact_hashes": [],
            "mode": "DETERMINISTIC_INFRASTRUCTURE",
        }
        with tempfile.TemporaryDirectory(prefix="objection-probe-") as directory:
            clock = ScenarioClock(scenario.as_of)
            broker = Broker(Jobflow(Path(directory) / "probe.sqlite3", demo=True, clock=clock))
            if scenario.delivered_artifacts:
                broker.producer = lambda _spec, _sources: [
                    (
                        item.filename,
                        item.media_type,
                        base64.b64decode(item.content_base64, validate=True),
                    )
                    for item in scenario.delivered_artifacts
                ]
            if (
                template
                and arm == "evolving_process"
                and (template["customer_id"], template["product_id"])
                == (scenario.customer_id, scenario.product_id)
            ):
                with broker.store.connect(write=True) as db:
                    version = ImprovementVersion.model_validate(template)
                    improvements.put(db, "version", version)
                    db.execute(
                        "INSERT INTO im_active VALUES(?,?,?)",
                        (version.customer_id, version.product_id, version.id),
                    )
            draft = None
            try:
                draft = broker.create_draft(
                    actor["customer"],
                    DraftCreate(
                        idempotency_key=uid("draft"),
                        intent=scenario.intent,
                        product_id=scenario.product_id,
                    ),
                )
                for source in scenario.sources:
                    draft = broker.upload(
                        actor["provider"],
                        draft.id,
                        SourceUpload(
                            idempotency_key=uid("source"),
                            expected_revision=draft.revision,
                            filename=source.filename,
                            content_base64=source.content_base64,
                        ),
                    )
                if scenario.historical_specification:
                    # A fixture import represents already accepted terms, not fresh intake consent.
                    # It exists only inside this temporary, simulated store.
                    with broker.store.connect(write=True) as db:
                        draft = storage.get(db, "br_drafts", draft.id, IntakeDraft)
                        draft.specification = scenario.historical_specification
                        draft.offered_price = Money(
                            amount_minor=1000, currency="USDSIM", decimals=2
                        )
                        draft.provider_actor_id = "provider"
                        draft.acceptance_digest = specification_digest(draft.specification)
                        broker._accept_draft(
                            db,
                            draft,
                            actor["customer"],
                            BrokerCommand(
                                idempotency_key=uid("historical"),
                                expected_revision=draft.revision,
                                verb="accept_specification",
                                digest=draft.acceptance_digest,
                                authorization_expires_at=clock()
                                + timedelta(seconds=scenario.authorization_seconds),
                            ),
                            historical_import=True,
                        )
                        storage.save(db, "br_drafts", draft)
                else:
                    customer = ConstrainedCustomer(scenario)
                    answered = set()
                    for _ in range(len(FIELDS) * 2 + 1):
                        pending = next(
                            (
                                q
                                for q in draft.questions
                                if q.answer_id is None and q.id not in answered
                            ),
                            None,
                        )
                        if pending is None and draft.unresolved_fields:
                            field = draft.unresolved_fields[0]
                            if any(
                                q.field == field and q.answer_id is None for q in draft.questions
                            ):
                                break
                            draft = broker.draft_command(
                                actor["controller"],
                                draft.id,
                                BrokerCommand(
                                    idempotency_key=uid("manual"),
                                    expected_revision=draft.revision,
                                    verb="clarify_intake",
                                    field=field,
                                ),
                            )
                            pending = next(
                                q
                                for q in reversed(draft.questions)
                                if q.field == field and q.answer_id is None
                            )
                        if pending is None:
                            break
                        value = customer.answer(pending)
                        answered.add(pending.id)
                        if value is None:
                            break
                        draft = broker.draft_command(
                            actor["customer"],
                            draft.id,
                            BrokerCommand(
                                idempotency_key=uid("answer"),
                                expected_revision=draft.revision,
                                verb="answer_intake",
                                question_id=pending.id,
                                value=value,
                            ),
                        )
                        result["customer_answers"] += 1
                    if draft.unresolved_fields:
                        result["outcome"] = (
                            "DECLINED" if scenario.customer_behavior == "decline" else "BLOCKED"
                        )
                    else:
                        draft = broker.draft_command(
                            actor["provider"],
                            draft.id,
                            BrokerCommand(
                                idempotency_key=uid("offer"),
                                expected_revision=draft.revision,
                                verb="offer",
                                capability="SUPPORTED",
                                price=Money(amount_minor=1000, currency="USDSIM", decimals=2),
                            ),
                        )
                        draft = broker.draft_command(
                            actor["customer"],
                            draft.id,
                            BrokerCommand(
                                idempotency_key=uid("accept"),
                                expected_revision=draft.revision,
                                verb="accept_specification",
                                digest=draft.acceptance_digest,
                                authorization_expires_at=clock()
                                + timedelta(seconds=scenario.authorization_seconds),
                            ),
                        )
                if draft.order_id:
                    result["accepted"] = True
                    record = broker.view(actor["customer"], draft.order_id)
                    frozen_snapshot = record.base_order.order.snapshot.model_dump(mode="json")
                    if record.base_order.order.ledger:
                        violations.append("capture_before_delivery")
                    record = broker.command(
                        actor["provider"],
                        record.id,
                        BrokerCommand(
                            idempotency_key=uid("produce"),
                            expected_revision=record.revision,
                            verb="produce",
                        ),
                    )
                    base = record.base_order.order
                    if base.ledger:
                        violations.append("capture_on_verification_alone")
                    result["outcome"] = (
                        base.data_verification.verdict
                        if base.data_verification
                        else "OPERATIONAL_FAILURE"
                    )
                    result["completed"] = bool(base.deliveries)
                    if result["outcome"] == "PASS":
                        record = broker.command(
                            actor["customer"],
                            record.id,
                            BrokerCommand(
                                idempotency_key=uid("accept-delivery"),
                                expected_revision=record.revision,
                                verb="accept_delivery",
                            ),
                        )
                    elif base.regeneration_pending:
                        record = broker.command(
                            actor["provider"],
                            record.id,
                            BrokerCommand(
                                idempotency_key=uid("correct"),
                                expected_revision=record.revision,
                                verb="produce",
                            ),
                        )
                    else:
                        clock.now += timedelta(seconds=600)
                        record = broker.view(actor["customer"], record.id)
                    base = record.base_order.order
                    result["financial_effects"] = len(base.ledger)
                    result["seller_rework_attempts"] = base.free_regenerations_used
                    result["required_review_tasks"] = sum(
                        task.state == "OPEN" for task in record.human_tasks
                    )
                    result["artifact_hashes"] = [
                        ref.sha256 for delivery in base.deliveries for ref in delivery.artifacts
                    ]
                    if base.snapshot.model_dump(mode="json") != frozen_snapshot:
                        violations.append("retroactive_contract_change")
                    if len(base.ledger) > 1 or any(
                        entry.amount.amount_minor != 1000 for entry in base.ledger
                    ):
                        violations.append("unauthorized_or_duplicate_financial_effect")
                    if result["outcome"] != "PASS" and base.ledger:
                        violations.append("nonpassing_capture")
                    if not scenario.historical_specification:
                        for requirement in base.snapshot.data_specification.requirements:
                            for field in FIELDS:
                                value = getattr(requirement.parameters, field)
                                if value is not None and value != ():
                                    actual = requirement.parameters.model_dump(mode="json")[field]
                                    if (
                                        actual
                                        != Parameters.model_validate(
                                            scenario.customer_answers
                                        ).model_dump(mode="json")[field]
                                    ):
                                        result["observed_answer_fidelity"] = False
                    result["specification_sha256"] = specification_digest(
                        base.snapshot.data_specification
                    )
                    result["payment_phase"] = base.payment_phase
                    result["order_state"] = base.order_state
                if draft:
                    trace = broker.events(actor["controller"], draft.id)
                    result["company_staff_touches"] = sum(
                        event["payload"].get("company_staff_touches", 0) for event in trace
                    )
            except (ValueError, KeyError, TypeError) as exc:
                result["outcome"] = "UNSUPPORTED"
                result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
            except Exception as exc:
                result["outcome"] = "ERROR"
                result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
                violations.append("application_error")
            result["trace"] = trace
            result["trace_sha256"] = digest(trace)
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        return result
