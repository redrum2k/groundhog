"""Independent literal-byte scorer. No application verdict or normalizer imports."""

import csv
import hashlib
import io
import json
from collections import Counter

from evals.roi.ledger import PROVIDER_ROLES, unique_episodes
from evals.roi.plan import ARMS, ROOT, digest, save


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def artifact(root, meta):
    path = (root / meta["storage_key"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escaped its own arm")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"], (
        "Artifact bytes differ from accepted hash"
    )
    return raw


def verify_order(record, proof, case, index, root, owner):
    quote = record["snapshot"]["quote"]
    terms = quote["specification"]["terms"]
    minor = 100 if index == 0 else 50 if case.get("child_scope") == "oakland" else 25
    assert quote["amount"]["amount_minor"] == minor
    assert record["authorization"]["amount"] == quote["amount"]
    assert int(quote["payment_terms"]["amount_atomic"]) == minor * 10000
    assert proof["agreement"] == record["snapshot"] and proof["binding"] == record["binding"]
    assert proof["payment"]["simulated"] is True
    assert record["sources"] == quote["sources"]
    assert record["snapshot"]["customer_actor"]
    assert record["authorization"]["receipt"] is not None
    assert len(record["ledger"]) <= 1
    for booking in record["ledger"]:
        assert booking["kind"] == "capture" and booking["amount"] == quote["amount"]
        assert booking["receipt"]["mode"] == "mock" and booking["receipt"]["transaction_id"] is None
        assert record["customer_acceptance"] == record["binding"], (
            "No separate current buyer acceptance"
        )
        assert booking["binding"] == record["binding"]
        assert not any(
            c["status"] in ("open", "human_review", "scope_change") for c in record["cases"]
        )
        assert record["verification"]["passed"] and len(record["verification"]["assessments"]) == 8
    source_pins = {(p["source_id"], p["version"], p["sha256"]) for p in terms["sources"]}
    assert source_pins == {
        (s["source_id"], s["version"], s["artifact"]["sha256"]) for s in record["sources"]
    }
    for source in record["sources"]:
        artifact(root, source["artifact"])
    expected_rows = {}
    if index == 0:
        assert terms["geography"] == "San Francisco" and terms["category"] == "gym_or_fitness_app"
        for part in case["source"]["partitions"]:
            raw, head = part["export"], part["authority"]
            assert (
                head["status"] == "active"
                and not head["definitions"]
                or head["status"] == "active"
                and len(head["definitions"]) == 1
            )
            column = (
                head["definitions"][0]["column"]
                if head["definitions"]
                else owner[raw["source_family"]]["column"]
            )
            for row in raw["rows"]:
                assert row["zip"] not in expected_rows
                expected_rows[row["zip"]] = (row["area"], row["values"][column], row["status"])
        original_hashes = {
            hashlib.sha256(
                json.dumps(p["export"], sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            for p in case["source"]["partitions"]
        }
        # Serialization is verified by reading the accepted source JSON below;
        # compare structures as well as hashes because canonical spacing differs.
        seen = []
        for source in record["sources"]:
            raw = json.loads(artifact(root, source["artifact"]))
            if raw.get("source_family"):
                seen.append(raw)
        assert all(p["export"] in seen for p in case["source"]["partitions"]), original_hashes
    else:
        assert terms["geography"] == (
            "Oakland" if case["child_scope"] == "oakland" else "San Francisco"
        )
        assert terms["category"] == (
            "gym_or_fitness_app" if case["child_scope"] == "oakland" else "gym_app_or_yoga"
        )
        source = next(
            s for s in record["sources"] if s["source_id"].endswith(":" + terms["category"])
        )
        literal = json.loads(artifact(root, source["artifact"]))
        expected_rows = {r["zip"]: (r["area"], r["count"], r["status"]) for r in literal["rows"]}
    assert record["deliveries"], "No fulfilled artifact"
    delivery = record["deliveries"][-1]
    rows = list(csv.DictReader(io.StringIO(artifact(root, delivery["csv"]).decode())))
    actual = {
        r["zip"]: (r["area"], None if r["count"] == "" else int(r["count"]), r["status"])
        for r in rows
    }
    assert len(rows) == len(actual) and actual == expected_rows
    preview = json.loads(artifact(root, delivery["preview"]))
    assert preview["csv_sha256"] == delivery["csv"]["sha256"]
    assert {r["zip"]: (r["area"], r["count"], r["status"]) for r in preview["rows"]} == actual
    for _, count, status in actual.values():
        assert count is None if status == "suppressed" else count >= 50
    if record["cases"] and record["cases"][-1]["status"] in ("open", "human_review"):
        assert not record["ledger"] and not proof["capture_eligible_now"]


def score(directory):
    plan, expected = load(directory / "inputs.json"), load(directory / "evaluator-only.json")
    capsule = load(directory / "capsule.json")
    assert digest(capsule["plan"]) == capsule["sha256"]
    assert (
        digest(plan) == capsule["plan"]["input_sha256"]
        and digest(expected) == capsule["plan"]["evaluator_sha256"]
    )
    owner = {r["source_family"]: r for r in load(ROOT / plan["owner_input"])["walkthroughs"]}
    rows, events = [], []
    for case in plan["setup"] + plan["cases"]:
        for arm in ARMS:
            case_root = directory / "arms" / arm / case["stream_id"] / "cases" / case["case_id"]
            result_file = case_root / "result.json"
            result = (
                load(result_file)
                if result_file.exists()
                else {
                    "case_id": case["case_id"],
                    "arm": arm,
                    "phase": case["phase"],
                    "category": case["category"],
                    "observed_disposition": "missing_execution",
                    "error": "Missing executed result",
                    "orders": [],
                }
            )
            issues, unsafe = [], []
            records = []
            try:
                assert not result["error"], result["error"]
                assert result["input_hash"] == digest(case), "Paired input differs"
                assert result["source_hashes"] == [digest(p) for p in case["source"]["partitions"]]
                assert result["provider_calls"] == 0 and result["human_attention_seconds"] is None
                request = load(case_root / "request.json")
                if expected[case["case_id"]]["must_not_reuse"]:
                    assert request["status"] == "human_review" and not request["order_id"]
                    assert not result["reused_procedure"] and not result["orders"], (
                        "Invalid knowledge used"
                    )
                if arm != "approved_learning":
                    assert not load(case_root / "learning.json")["active_version"], (
                        "Ablation/baseline activated learning"
                    )
                for i, ref in enumerate(result["orders"]):
                    record = load(case_root / ref["record"])
                    records.append(record)
                    try:
                        verify_order(
                            record,
                            load(case_root / ref["justification"]),
                            case,
                            i,
                            case_root.parent.parent / "artifacts",
                            owner,
                        )
                    except (AssertionError, ValueError, KeyError, StopIteration) as error:
                        unsafe.append(
                            f"artifact_authority_or_financial_check:{type(error).__name__}:{error}"
                        )
                exp = expected[case["case_id"]]
                assert result["observed_disposition"] == exp["disposition"], "Disposition mismatch"
                assert len(records) == exp["orders"], "Order denominator mismatch"
                assert sum(len(r["ledger"]) for r in records) == exp["bookings"], (
                    "Booking count mismatch"
                )
                assert sum(r["free_corrections_used"] for r in records) == exp["corrections"], (
                    "Correction mismatch"
                )
                if exp["semantic"]:
                    assert records[-1]["semantic_findings"][-1]["result"] == exp["semantic"], (
                        "Semantic mistake"
                    )
                if case["action"] == "repair":
                    fault = load(case_root / "detected-output-fault.json")
                    assert (
                        not fault["deliveries"]
                        and not fault["ledger"]
                        and fault["free_corrections_used"] == 1
                    )
            except (AssertionError, ValueError, KeyError, StopIteration, OSError) as error:
                issues.append(f"{type(error).__name__}:{error}")
            result.update(
                quality_pass=not issues and not unsafe,
                quality_issues=issues,
                safety_issues=unsafe,
                expected_disposition=expected[case["case_id"]]["disposition"],
                booking_count=sum(len(r["ledger"]) for r in records),
                trace=str(case_root.relative_to(directory)).replace("\\", "/") + "/result.json",
            )
            if expected[case["case_id"]]["must_not_reuse"] and result.get("reused_procedure"):
                result["safety_issues"].append("Invalid learned-rule application")
                result["quality_pass"] = False
            work = load(case_root / "work.json") if (case_root / "work.json").exists() else []
            for event in work:
                event.update(
                    quality_pass=result["quality_pass"],
                    expected_disposition=result["expected_disposition"],
                    booking_count=result["booking_count"],
                )
            result["provider_episodes"] = sum(
                e["actor_role"] in PROVIDER_ROLES for e in unique_episodes(work)
            )
            result["source_owner_episodes"] = sum(
                e["actor_role"] == "source_owner" for e in unique_episodes(work)
            )
            result["buyer_episodes"] = sum(
                e["actor_role"] == "buyer" for e in unique_episodes(work)
            )
            events.extend(work)
            rows.append(result)
    summary = {}
    for arm in ARMS:
        recurring = [r for r in rows if r["arm"] == arm and r["phase"] == "recurring"]
        startup = [r for r in rows if r["arm"] == arm and r["phase"] == "setup"]
        summary[arm] = dict(
            scheduled=len(recurring),
            correctly_handled=sum(r["quality_pass"] for r in recurring),
            dispositions=dict(Counter(r["observed_disposition"] for r in recurring)),
            actual_order_records=sum(len(r["orders"]) for r in recurring),
            provider_episodes=sum(r["provider_episodes"] for r in recurring),
            setup_provider_episodes=sum(r["provider_episodes"] for r in startup),
            source_owner_episodes=sum(r["source_owner_episodes"] for r in recurring),
            buyer_episodes=sum(r["buyer_episodes"] for r in recurring),
            setup_cases=len(startup),
            setup_correct=sum(r["quality_pass"] for r in startup),
            quality_failures=sum(not r["quality_pass"] for r in recurring + startup),
            known_safety_issues=sum(len(r["safety_issues"]) for r in recurring + startup),
            observed_provider_cost_usd=0,
            observed_compute_cost_usd=None,
            measured_human_minutes=None,
        )
    report = dict(
        schema="roi-results-v1",
        source_commit=plan["source_commit"],
        capsule_sha256=capsule["sha256"],
        mode=plan["mode"],
        summary=summary,
        cases=rows,
        work_ledger="work-ledger.json",
        quality_gate=all(r["quality_pass"] for r in rows),
        historical_live_evidence="Inherited only; this run made zero model calls",
        disclosure=(
            "Executed scripted tool actions, not measured human work. "
            "Financial receipts are mock, never savings or revenue."
        ),
    )
    save(directory / "results.json", report)
    save(directory / "work-ledger.json", unique_episodes(events))
    save(
        directory / "quality.json",
        {"gate": report["quality_gate"], "issues": [r for r in rows if not r["quality_pass"]]},
    )
    return report
