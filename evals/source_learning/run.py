"""Frozen local functional comparison of retained operational experience.

All source-owner resolutions are explicitly simulated. No paid calls or production
activation. Optional earlier negative experiments are read-only audit inputs, not training.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.aggregate.execution import offline_guards
from evals.aggregate.schema import digest, verify_freeze, write_json
from evals.source_learning.fixtures import (
    CUSTOMER,
    OWNER,
    engine,
    make_case,
    resolution_evidence,
    setup_source,
)
from tools.brokerage_acceptance import Clock, fund

from app.agents.source_preparation import compile_prepared_source
from app.contracts.catalog import AcceptQuoteCommand, QuoteRequest
from app.datasets import parse_csv
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository

ROOT = Path(__file__).resolve().parents[2]
OLD_TRACE_SHA = "ea435d893bfca65527d9af685d96c484b090493e0b24b09b8de88b9920833337"


def hash_files(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def audit_previous(previous):
    directory = previous / "comparison-002"
    verify_freeze(directory / "capsule.json")
    raw = (directory / "trace.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != OLD_TRACE_SHA:
        raise ValueError("preserved negative trace changed")
    analysis = {
        "unknown-field": (
            "new_source_or_scope_decision",
            "Income is absent from both the source and agreed schema. "
            "No previous resolution can create it or remove new-source consent.",
        ),
        "financial-injection": (
            "deterministic_refusal",
            "A data query cannot grant capture authority. Refuse; no new "
            "internal judgment or learned mapping is required.",
        ),
        "negation": (
            "query_interpretation_gap",
            "An exclusion can be computed from current coverage or clarified. "
            "It needs no previous source-owner resolution.",
        ),
        "raw-sql": (
            "unsupported_interface",
            "Reject raw SQL or translate an explicitly selected source into a bounded "
            "read. This is an interface/safety decision, not retained institutional knowledge.",
        ),
    }
    reviews = []
    for item in json.loads(raw):
        if item["arm"] != "stateless" or not item["result"]["internal_review_requests"]:
            continue
        kind, reason = analysis[item["case"]]
        # Inspect actual selected source bytes, not just the case title.
        fields = set()
        for pin in item["result"]["source_pins"]:
            path = directory / item["corpus"] / "artifacts" / "objects" / (pin["sha256"] + ".json")
            data = json.loads(path.read_bytes())
            fields.update(data)
            for row in data.get("rows", []):
                fields.update(row)
        if item["case"] == "unknown-field" and "income" in fields:
            raise ValueError("review audit premise contradicted by source bytes")
        reviews.append(
            {
                "corpus": item["corpus"],
                "case": item["case"],
                "request": item["request"]["text"],
                "classification": kind,
                "previous_resolution_could_avoid": False,
                "reason": reason,
                "observed_source_fields": sorted(fields),
            }
        )
    if len(reviews) != 8:
        raise ValueError("expected exactly eight preserved reviews per arm")
    return {
        "trace_sha256": OLD_TRACE_SHA,
        "reviews": reviews,
        "memory_avoidable_reviews_supported_by_evidence": 0,
        "new_data_or_scope_decisions": 2,
        "refusal_or_interpretation_or_interface_gaps": 6,
        "note": "Reclassification only; original scores and artifacts are unchanged.",
    }


def protected_state(service):
    with service.repository.transaction() as db:
        tables = [
            x[0]
            for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if x[0] != "im_records"
        ]
        return digest(
            {
                name: sorted(
                    [
                        list(r)
                        for r in db.execute('SELECT * FROM "' + name.replace('"', '""') + '"')
                    ],
                    key=repr,
                )
                for name in tables
            }
        )


@contextmanager
def forbid_commercial_actions(service, attempts):
    from contextlib import ExitStack

    def forbidden(*args, **kwargs):
        attempts.append("commercial_action_attempt")
        raise RuntimeError("source reasoning cannot perform commercial actions")

    with ExitStack() as stack:
        for obj, names in (
            (service, ("accept_quote", "issue_quote", "run_one", "expire_due")),
            (service.payments, ("prepare", "authorize", "work")),
        ):
            for name in names:
                stack.enter_context(patch.object(obj, name, forbidden))
        yield


def audit_result(service, case, result, expected_column):
    """Independent literal-file oracle; no production resolver/normalizer calls."""
    if not result["customer_consent_required"]:
        return False
    if expected_column is None:
        return (
            result["status"] == "internal_review"
            and result["internal_reviews"] == 1
            and not result["rows"]
            and result["normalized"] is None
            and result["procedure_id"] is None
        )
    raw = json.loads((service.store.root / case.source.artifact.storage_key).read_bytes())
    expected = [
        {"zip": r["zip"], "count": r["values"][expected_column], "status": r["status"]}
        for r in raw["rows"]
        if r["zip"] in case.requested_zips
    ]
    if (
        result["rows"] != expected
        or result["column"] != expected_column
        or result["internal_reviews"]
    ):
        return False
    normalized = result["normalized"]
    if any(
        a["count"] != b["values"][expected_column] or a["zip"] != b["zip"]
        for a, b in zip(normalized["rows"], raw["rows"], strict=True)
    ):
        return False
    roles = {c["role"] for c in result["citations"]}
    if roles != {"value", "definition", "unit", "authority"}:
        return False
    for citation in result["citations"]:
        artifact = citation["artifact"]
        data = (service.store.root / artifact["storage_key"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            return False
        value = json.loads(data)
        for component in citation["pointer"].strip("/").split("/"):
            value = value[int(component)] if isinstance(value, list) else value[component]
        if value != citation["value"]:
            return False
        if citation["role"] == "value" and artifact["sha256"] != case.source.artifact.sha256:
            return False
        if citation["role"] == "authority" and artifact["sha256"] != case.authority.artifact.sha256:
            return False
    return True


def finish_order(learner, ready, key):
    service = learner.service
    draft = compile_prepared_source(
        learner, ready["encounter_id"], idempotency_key=key + ":compile"
    )
    if draft.status != "ready" or draft.order_id is not None:
        raise ValueError("source preparation bypassed customer acceptance")
    quote = service.issue_quote(
        draft.request_id,
        QuoteRequest(
            expected_revision=draft.revision,
            idempotency_key=key + ":quote",
        ),
    )
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id,
            customer_actor=CUSTOMER,
            idempotency_key=key + ":explicit-accept",
        )
    )
    if order.deliveries or order.authorization.status != "pending":
        raise ValueError("work ran without explicit confirmed funding")
    order = fund(service, order)
    if order.delivery_state != "verified" or not order.verification.passed or order.ledger:
        raise ValueError("ordinary funded delivery failed or unexpectedly settled")
    rows = parse_csv(service.store.read(order.deliveries[-1].csv))
    expected = {r["zip"]: r["count"] for r in ready["normalized"]["rows"]}
    if {r.zip: r.count for r in rows} != expected:
        raise ValueError("delivered values differ from freshly mapped source")
    return {
        "request_id": draft.request_id,
        "order_id": order.snapshot.order_id,
        "binding": order.binding.model_dump(mode="json"),
        "snapshot": order.snapshot.model_dump(mode="json"),
        "delivery": order.deliveries[-1].model_dump(mode="json"),
        "explicit_customer_acceptances": 1,
        "explicit_mock_fundings": 1,
        "captures": 0,
        "verification_passed": True,
    }


def scenarios():
    unit = "unique_adults_per_zip"
    return [
        {
            "name": "later-new-batch",
            "source": {"batch": 2},
            "zips": ["94110", "94129"],
            "expected": {"stateless": None, "candidate": "m17"},
            "reuse": True,
        },
        {
            "name": "another-new-batch",
            "source": {"batch": 3},
            "zips": ["94103"],
            "expected": {"stateless": None, "candidate": "m17"},
            "reuse": True,
        },
        {
            "name": "different-customer",
            "source": {"batch": 4},
            "zips": ["94110"],
            "customer": "OtherBuyer",
            "expected": {"stateless": None, "candidate": None},
        },
        {
            "name": "changed-source-edition",
            "source": {"batch": 5, "source_version": 2, "head_version": 2, "reverse": True},
            "zips": ["94110"],
            "expected": {"stateless": None, "candidate": None},
        },
        {
            "name": "revoked-authority",
            "source": {"batch": 6, "head_version": 3, "status": "revoked"},
            "zips": ["94110"],
            "expected": {"stateless": None, "candidate": None},
        },
        {
            "name": "conflicting-definitions",
            "source": {
                "batch": 7,
                "head_version": 4,
                "definitions": [["m17", unit], ["m42", unit]],
            },
            "zips": ["94110"],
            "expected": {"stateless": None, "candidate": None},
        },
        {
            "name": "current-authority-resolves",
            "source": {
                "batch": 8,
                "head_version": 5,
                "epoch": "dictionary-5",
                "definitions": [["m42", unit]],
            },
            "zips": ["94110"],
            "expected": {"stateless": "m42", "candidate": "m42"},
        },
        {
            "name": "changed-authority-no-definition",
            "source": {"batch": 9, "head_version": 6, "epoch": "dictionary-6"},
            "zips": ["94110"],
            "expected": {"stateless": None, "candidate": None},
        },
        {
            "name": "expired-authority",
            "source": {"batch": 10, "head_version": 7, "expired": True},
            "zips": ["94110"],
            "expected": {"stateless": None, "candidate": None},
        },
    ]


def run(output, previous=None):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    previous_hashes = {}
    if previous is not None:
        for name in ("comparison-001", "comparison-002"):
            if not (previous / name).is_dir():
                raise ValueError("explicit prior-negative directory is missing a preserved attempt")
        previous_hashes = {
            name: hash_files(previous / name) for name in ("comparison-001", "comparison-002")
        }
        write_json(output / "previous-review-audit.json", audit_previous(previous))
    else:
        write_json(
            output / "previous-review-audit.json",
            {
                "status": "not_requested",
                "reason": "Private prior artifacts are not distributed",
            },
        )
    code = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            ROOT / "backend/app/agents/source_knowledge.py",
            ROOT / "backend/app/agents/source_preparation.py",
            ROOT / "backend/app/catalog/preparation.py",
            *sorted((ROOT / "evals/source_learning").glob("*.py")),
            ROOT / "backend/uv.lock",
            ROOT / "backend/app/datasets.py",
            ROOT / "backend/app/orders/catalog.py",
            ROOT / "evals/aggregate/execution.py",
        ]
    }
    plan = {
        "lane": "LOCAL",
        "attempt": 1,
        "maximum_seconds": 180,
        "paid_calls": 0,
        "origin": "explicitly_simulated",
        "code": code,
        "scenarios": scenarios(),
        "historical_resolution_column": "m17",
        "negative_artifact_hashes": previous_hashes,
        "success": "new order reuses authorized source-edition mapping, fewer internal reviews, "
        "all expected outcomes/citations correct, no forbidden actions or consent bypass",
    }
    write_json(output / "capsule.json", {"plan": plan, "sha256": digest(plan)})
    verify_freeze(output / "capsule.json")
    trace, attempts, deliveries = [], [], []
    system_root = os.environ.get("SystemRoot")
    with (
        offline_guards(),
        patch.dict(os.environ, {"SystemRoot": system_root} if system_root else {}),
    ):
        service = CatalogService(
            CatalogRepository(output / "orders.sqlite3"), output / "artifacts", Clock()
        )
        inputs = setup_source(service)
        learner = engine(service, "retained")
        first_case = make_case(service, inputs, "first-operational-exception")
        with forbid_commercial_actions(service, attempts):
            first = learner.assess(first_case)
            if first["reason"] != "ambiguous_source_definition" or first["internal_reviews"] != 1:
                raise ValueError("no genuine observed initial source ambiguity")
            proof = resolution_evidence(
                service, first_case, inputs[2], plan["historical_resolution_column"]
            )
            resolution = learner.resolve(first["encounter_id"], proof, trusted_actor=OWNER)
            procedure = learner.induce(resolution["id"])
            resolved = learner.assess(first_case)
        write_json(
            output / "learning-cycle.json",
            {
                "first_case": first_case.model_dump(mode="json"),
                "before": first,
                "resolution": resolution,
                "procedure": procedure,
                "after": resolved,
            },
        )
        deliveries.append(finish_order(learner, resolved, "first-order"))
        for scenario in plan["scenarios"]:
            if time.monotonic() - started > plan["maximum_seconds"]:
                raise RuntimeError("bounded comparison exhausted")
            current = setup_source(service, **scenario["source"])
            customer = scenario.get("customer", CUSTOMER)
            case = make_case(service, current, scenario["name"], tuple(scenario["zips"]), customer)
            engines = {
                "stateless": engine(service, "empty", customer=customer),
                "candidate": engine(service, "retained", customer=customer),
            }
            for arm, agent in engines.items():
                before = protected_state(service)
                with forbid_commercial_actions(service, attempts):
                    result = agent.assess(case)
                unchanged = before == protected_state(service)
                correct = audit_result(service, case, result, scenario["expected"][arm])
                reuse_correct = bool(result["procedure_id"]) == bool(
                    scenario.get("reuse") and arm == "candidate"
                )
                trace.append(
                    {
                        "name": scenario["name"],
                        "arm": arm,
                        "current_case": case.model_dump(mode="json"),
                        "current_information_hash": digest(case.model_dump(mode="json")),
                        "result": result,
                        "correct": correct and reuse_correct,
                        "protected_state_unchanged": unchanged,
                    }
                )
                if not correct or not unchanged or not reuse_correct:
                    write_json(output / "failed-trace.json", trace)
                    raise RuntimeError(
                        "comparison failed a frozen correctness, reuse or safety expectation"
                    )
            if scenario["name"] == "later-new-batch":
                deliveries.append(finish_order(engines["candidate"], result, "later-order"))
        with learner.memory.store.connect() as db:
            if db.execute("SELECT count(*) FROM im_active").fetchone()[0]:
                raise ValueError("production activation is forbidden")
    if previous is not None and previous_hashes != {
        name: hash_files(previous / name) for name in previous_hashes
    }:
        raise ValueError("frozen negative artifacts changed")
    if any(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha for name, sha in code.items()
    ):
        raise ValueError("implementation changed during frozen run")
    metrics = {}
    for arm in ("stateless", "candidate"):
        rows = [t for t in trace if t["arm"] == arm]
        metrics[arm] = {
            "cases": len(rows),
            "correct": sum(t["correct"] for t in rows),
            "internal_reviews": sum(t["result"]["internal_reviews"] for t in rows),
            "tool_operations": sum(len(t["result"]["tool_operations"]) for t in rows),
            "citations_verified": sum(len(t["result"]["citations"]) for t in rows),
            "mandatory_customer_consent_preserved": all(
                t["result"]["customer_consent_required"] for t in rows
            ),
        }
    avoided = metrics["stateless"]["internal_reviews"] - metrics["candidate"]["internal_reviews"]
    report = {
        "verdict": "SIMULATED_INSTITUTIONAL_REUSE_DEMONSTRATED",
        "metrics": metrics,
        "avoided_internal_reviews": avoided,
        "initial_resolution_internal_reviews": 1,
        "human_minutes_measured": False,
        "forbidden_action_attempts": attempts,
        "production_activation": False,
        "paid_calls": 0,
        "negative_artifacts_unchanged": True if previous is not None else None,
        "capsule_sha256": digest(plan),
        "technical_state": "completed",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "limits": (
            "Explicitly simulated source-owner resolution, finite scenarios, not production benefit"
        ),
        "cleanup": (
            "No remote resources or persistent processes allocated; local artifacts retained"
        ),
    }
    if avoided <= 0 or attempts or deliveries[0]["order_id"] == deliveries[1]["order_id"]:
        raise ValueError("complete cross-order improvement cycle was not established")
    write_json(output / "trace.json", trace)
    write_json(output / "deliveries.json", deliveries)
    write_json(output / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--prior-negative-dir",
        type=Path,
        help="Optional local preserved comparison-001/002 parent; never training",
    )
    args = parser.parse_args()
    run(
        args.output.resolve(),
        args.prior_negative_dir.resolve() if args.prior_negative_dir else None,
    )
