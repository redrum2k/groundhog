"""Read-only byte/usage audit and generated public evidence for this qualification.

No SDK, model requests, expected-label runtime injection or new evaluation engine.
Reuse the independent exact-cell audit instead of trusting the runtime resolver.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import sqlite3
from pathlib import Path

from aggregate_qualification_access import LEDGER, OUTPUT, WINDOW

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "primary_audit", ROOT / "tools/audit_primary_evidence.py"
)
primary_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(primary_audit)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cost_micro(usage):
    cache = usage.get("cache_creation") or {}
    write = (cache.get("ephemeral_5m_input_tokens", 0) or 0) * 5 + (
        cache.get("ephemeral_1h_input_tokens", 0) or 0
    ) * 8
    if not cache:
        write = (usage.get("cache_creation_input_tokens", 0) or 0) * 8
    return (
        usage["input_tokens"] * 4
        + usage["output_tokens"] * 20
        + write
        + ((usage.get("cache_read_input_tokens", 0) or 0) + 4) // 5
    )


def audit():
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        ledger = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM calls WHERE window_id=? ORDER BY started_at", (WINDOW,)
            )
        ]
        totals = dict(
            db.execute(
                "SELECT count(*) requests, sum(status='RESERVED') active, "
                "sum(actual_micro_usd) known_micro, "
                "sum(coalesce(actual_micro_usd,reserved_micro_usd)) committed_micro FROM calls"
            ).fetchone()
        )
    unmatched = {row["id"]: row for row in ledger}
    records, cases, cohorts, files, artifacts = [], [], [], {}, {}
    for plan_path in sorted(OUTPUT.glob("*/frozen-plan.json")):
        folder = plan_path.parent
        plan = load(plan_path)
        summary = load(folder / "results.json")
        assert plan["source_sha256"] == summary["source_sha256"], "Runtime changed during cohort"
        cohorts.append(
            dict(
                cohort=folder.name,
                plan=plan,
                results=summary,
                supervisor=load(folder / "supervisor.json"),
                model_availability=load(folder / "model-availability.json"),
            )
        )
        assert len(summary["cases"]) == len(plan["intake"]) + len(plan["disputes"])
        for recipe in (*plan["intake"], *plan["disputes"]):
            case_dir = folder / recipe["id"]
            result_path = case_dir / "result.json"
            result = (
                load(result_path)
                if result_path.exists()
                else load(folder / (recipe["id"] + "-failure.json"))
            )
            references_checked = 0
            call_rows = []
            for path in sorted(case_dir.glob("call-*.json")):
                record = load(path)
                call_rows.append(
                    dict(
                        call_id=record["call_id"],
                        raw=record["raw_response"],
                        latency_seconds=record["latency_seconds"],
                    )
                )
            if (case_dir / "attempt.json").exists():
                attempt = load(case_dir / "attempt.json")
                order = load(case_dir / "order.json")
                assert not order["ledger"] and order["free_corrections_used"] == 0
                assert order["authorization"]["status"] == "mock_authorized"
                assert all(a["result"] == "PASS" for a in order["verification"]["assessments"])
                for key in ("candidate", "effective"):
                    finding = attempt[key]
                    if finding:
                        for ref in finding["citations"] + finding["conflicting_evidence"]:
                            primary_audit.exact_cell(case_dir, order, ref)
                            references_checked += 1
                call_rows.append(
                    dict(
                        call_id=None,
                        raw=attempt["raw_response"],
                        latency_seconds=attempt["elapsed_seconds"],
                    )
                )
                # Publish actual synthetic source/output bytes, not only runtime verdicts.
                for artifact in order["artifacts"]:
                    raw = (case_dir / "artifacts" / artifact["storage_key"]).read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    assert digest == artifact["sha256"]
                    artifacts[digest] = dict(
                        media_type=artifact["media_type"], text=raw.decode("utf-8")
                    )
            case_cost = 0
            for call in call_rows:
                raw = call["raw"]
                if raw is None:
                    if call["call_id"]:
                        row = unmatched.pop(call["call_id"])
                        assert row["status"] != "RESERVED"
                        records.append(
                            dict(
                                cohort=folder.name,
                                case=recipe["id"],
                                call_id=row["id"],
                                status=row["status"],
                                reserved_usd=row["reserved_micro_usd"] / 1e6,
                                raw_response_missing=True,
                            )
                        )
                    continue
                usage = raw["usage"]
                assert raw["model"] == "claude-opus-5-5"
                assert usage.get("service_tier", "standard") == "standard"
                assert usage.get("inference_geo", "global") == "global"
                if call["call_id"]:
                    row = unmatched.pop(call["call_id"])
                else:
                    matches = [
                        r
                        for r in unmatched.values()
                        if r["usage_json"] and json.loads(r["usage_json"]) == usage
                    ]
                    assert matches, "Response has no corresponding cumulative-ledger usage"
                    row = unmatched.pop(matches[0]["id"])
                assert json.loads(row["usage_json"]) == usage
                computed = cost_micro(usage)
                assert computed == row["actual_micro_usd"]
                case_cost += computed
                records.append(
                    dict(
                        cohort=folder.name,
                        case=recipe["id"],
                        call_id=row["id"],
                        status=row["status"],
                        model=raw["model"],
                        stop_reason=raw["stop_reason"],
                        usage=usage,
                        latency_seconds=call["latency_seconds"],
                        estimated_cost_usd=computed / 1e6,
                    )
                )
            cases.append(
                dict(
                    cohort=folder.name,
                    result=result,
                    references_checked=references_checked,
                    estimated_cost_usd=case_cost / 1e6,
                )
            )
            for path in sorted(case_dir.glob("*.json")):
                files[path.relative_to(OUTPUT).as_posix()] = load(path)
    assert not unmatched, "Some charged calls are absent from the saved qualification evidence"
    assert not totals["active"], "Outstanding reservations must remain visible/unresolved"
    usage_records = [r for r in records if "usage" in r]
    return dict(
        kind="ACTUAL_ANTHROPIC_SCENARIO_QUALIFICATION_NOT_INDEPENDENT_HOLDOUT",
        authorization=load(OUTPUT / "authorization.json"),
        cohorts=cohorts,
        cases=cases,
        calls=records,
        call_count=len(ledger),
        input_tokens=sum(r["usage"]["input_tokens"] for r in usage_records),
        output_tokens=sum(r["usage"]["output_tokens"] for r in usage_records),
        thinking_tokens_included_in_output=sum(
            (r["usage"].get("output_tokens_details") or {}).get("thinking_tokens", 0)
            for r in usage_records
        ),
        known_cost_usd=sum(r["actual_micro_usd"] or 0 for r in ledger) / 1e6,
        conservative_cost_usd=sum(
            r["actual_micro_usd"] if r["actual_micro_usd"] is not None else r["reserved_micro_usd"]
            for r in ledger
        )
        / 1e6,
        cumulative_ledger=dict(
            requests=totals["requests"],
            active=totals["active"],
            known_cost_usd=totals["known_micro"] / 1e6,
            conservative_committed_usd=totals["committed_micro"] / 1e6,
        ),
        ledger_reconciled=True,
        method="Independent hashlib/CSV/JSON reads plus read-only ledger reconciliation",
        files=files,
        artifacts_by_sha256=artifacts,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    result = audit()
    content = json.dumps(result, indent=2) + "\n"
    assert not re.search(r"sk-ant-[A-Za-z0-9_-]{20,}|-----BEGIN .*PRIVATE KEY", content)
    target = (
        ROOT / "docs/evidence/aggregate-qualification-20261024.json"
        if args.publish
        else OUTPUT / "independent-audit.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(content)
    summary = {
        k: v
        for k, v in result.items()
        if k not in {"authorization", "cohorts", "files", "artifacts_by_sha256", "calls", "cases"}
    }
    summary["cases"] = [
        dict(
            cohort=c["cohort"],
            case=c["result"]["case"],
            raw=c["result"].get("raw"),
            effective=c["result"].get("effective"),
            acceptance=c["result"].get("acceptance_pass"),
            cost=c["estimated_cost_usd"],
            references=c["references_checked"],
        )
        for c in result["cases"]
    ]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
