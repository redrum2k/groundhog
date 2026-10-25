"""Freeze paired public inputs and separate evaluator expectations before execution."""

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from tools.brokerage_acceptance import Clock
from tools.learning_examples import example_bundle

from app.agents.source_knowledge import VendorExport

ROOT = Path(__file__).resolve().parents[2]
ARMS = ("operator", "no_learning", "approved_learning")
PROMPT = "SF adults 25-34, gym membership or fitness app use, counts by ZIP."
SEED = 20261025
KINDS = ("repeat", "documented", "defect", "objection", "scope", "exception")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)


def source_input(batch, mode="normal", *, seed=SEED):
    bundle = example_bundle(Clock()(), batch).model_dump(mode="json")
    rng = random.Random(seed + batch)
    for index, part in enumerate(bundle["partitions"]):
        raw, head = part["export"], part["authority"]
        for row in raw["rows"]:
            if row["status"] == "released":
                row["values"] = {k: v + rng.randrange(11, 98) for k, v in row["values"].items()}
        if batch % 2 == 0:
            rng.shuffle(raw["rows"])
        column = ("v_count", "p_adults")[index]
        if mode == "documented":
            head["definitions"] = [{"column": column, "unit": "unique_adults_per_zip"}]
        elif mode in ("revoked", "conflict"):
            head["status"] = mode
        elif mode == "expired":
            head["valid_until"] = "2026-10-23T12:00:00Z"
        elif mode == "changed_schema":
            raw["schema_version"] += 1
            head["source_version"] = raw["schema_version"]
            head["schema_hash"] = VendorExport.model_validate(raw).schema_hash
        elif mode == "changed_epoch":
            head["epoch"] = "new-dictionary-without-current-definition"
        elif mode == "conflicting_definitions":
            head["definitions"] = [
                {"column": c, "unit": "unique_adults_per_zip"} for c in raw["columns"]
            ]
    return bundle


def make_plan(seed=SEED):
    cases = []

    def add(kind, stream="recurring", mode="normal", action="capture", **extra):
        index = len(cases)
        identifier = f"case-{index + 1:03d}"
        case = dict(
            case_id=identifier,
            stream_id=stream,
            category=kind,
            phase="recurring",
            prompt=PROMPT,
            source_mode=mode,
            action=action,
            **extra,
        )
        case["source"] = source_input(index + 10, mode, seed=seed)
        cases.append(case)

    for _ in range(20):
        add("repeat")
    for _ in range(10):
        add("documented", "documentation", "documented")
    for _ in range(8):
        add("defect", action="repair")
    questions = [
        "Does standalone yoga count?",
        "Is standalone yoga included in our accepted scope?",
        "Under our accepted scope, does standalone yoga count?",
        "Does our agreed contract include yoga studios?",
        "ZIP 94110 is missing from the delivered CSV.",
        "ZIP 94103 is absent from the dataset.",
        "You omitted ZIP 94111 from the delivery.",
        "Does standalone yoga count?",
    ]
    for i, text in enumerate(questions):
        add(
            "objection",
            action="question",
            complaint=text,
            complaint_field="coverage" if i in (4, 5, 6) else "category",
            target=("94110", "94103", "94111")[i - 4] if i in (4, 5, 6) else "dataset",
            child_scope="yoga" if i == 7 else None,
        )
    for i in range(6):
        add("scope", action="expand", child_scope="oakland" if i % 2 == 0 else "yoga")
    for mode in (
        "revoked",
        "conflict",
        "expired",
        "changed_schema",
        "changed_epoch",
        "conflicting_definitions",
    ):
        add("exception", "attack-" + mode, mode, "source_hold")
    for text in (
        "Do these aggregates prove each membership is still paid today?",
        "Can you establish that no person appears in more than one ZIP?",
    ):
        add(
            "exception",
            action="unavailable",
            complaint=text,
            complaint_field="category",
            target="dataset",
        )
    streams = list(dict.fromkeys(c["stream_id"] for c in cases))
    setup = [
        dict(
            case_id="setup-" + stream,
            stream_id=stream,
            category="onboarding",
            phase="setup",
            prompt=PROMPT,
            source_mode="normal",
            action="capture",
            source=source_input(1, seed=seed),
        )
        for stream in streams
        if stream != "documentation"
    ]
    expected = {}
    for case in setup + cases:
        hold = case["action"] in ("source_hold", "unavailable")
        expected[case["case_id"]] = {
            "disposition": "held_before_acceptance"
            if case["action"] == "source_hold"
            else "held_funded"
            if hold
            else "fulfilled",
            "orders": 0 if case["action"] == "source_hold" else 2 if case.get("child_scope") else 1,
            "bookings": 0 if hold else 2 if case.get("child_scope") else 1,
            "semantic": "UNKNOWN"
            if case["action"] == "unavailable"
            else "PASS"
            if case.get("child_scope") == "yoga" and case["action"] == "question"
            else "FAIL"
            if case["action"] == "question"
            else None,
            "corrections": int(case["action"] == "repair"),
            "must_not_reuse": case["action"] == "source_hold",
        }
    return {
        "schema": "roi-workload-v1",
        "seed": seed,
        "lane": "LOCAL",
        "mode": "offline_rules_mock_payments",
        "market": "Recurring aggregate-data broker with two bounded synthetic source families",
        "population_claim": "Chosen engineering coverage suite, not empirical prevalence",
        "arms": list(ARMS),
        "cases": cases,
        "setup": setup,
        "counts": dict(Counter(c["category"] for c in cases)),
        "scheduled_cases": len(cases),
        "setup_cases": len(setup),
        "restart_after_recurring_case": "case-010",
        "human_timing": "not_collected",
        "max_paid_calls": 0,
        "max_cost_usd": 0,
        "max_seconds": 1200,
        "inference_comparison": "All arms use the same offline compiler/assessor and payment gates",
        "operator": (
            "Scripted competent tool proxy with its own chronological source glossary; "
            "not a timed human"
        ),
        "owner_input": "docs/examples/judge-owner-walkthroughs.json",
    }, expected


def freeze(directory, commit):
    directory.mkdir(parents=True, exist_ok=False)
    plan, expected = make_plan()
    plan["source_commit"] = commit
    plan["owner_input_sha256"] = hashlib.sha256(
        (ROOT / plan["owner_input"]).read_bytes()
    ).hexdigest()
    save(directory / "inputs.json", plan)
    save(directory / "evaluator-only.json", expected)
    capsule = {
        "lane": "LOCAL",
        "attempt": 1,
        "source_commit": commit,
        "input_sha256": digest(plan),
        "evaluator_sha256": digest(expected),
        "artifact_contract": [
            "results.json",
            "work-ledger.json",
            "quality.json",
            "report.html",
            "arms/*/*/orders.sqlite3",
        ],
        "maximum_seconds": plan["max_seconds"],
        "paid_calls": 0,
        "supervision": "Bounded synchronous local CLI; no persistent service or remote resources",
    }
    save(directory / "capsule.json", {"plan": capsule, "sha256": digest(capsule)})
    return capsule
