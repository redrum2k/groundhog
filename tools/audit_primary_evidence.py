"""Independent byte/usage audit of saved primary evidence; never dispatches work."""

import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "backend/artifacts/primary-followup"
LEDGER = Path("D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def exact_cell(case, order, ref):
    artifact = next(a for a in order["artifacts"] if a["artifact_id"] == ref["artifact_id"])
    raw = (case / "artifacts" / artifact["storage_key"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref["sha256"] == artifact["sha256"]
    if artifact["media_type"] == "text/csv":
        data = {"rows": list(csv.DictReader(io.StringIO(raw.decode())))}
        assert ref["source_id"] == "delivery"
        delivery = next(
            d for d in order["deliveries"] if d["csv"]["artifact_id"] == ref["artifact_id"]
        )
        assert ref["version"] == delivery["version"]
    else:
        data = json.loads(raw)
        assert data["source_id"] == ref["source_id"] and data["version"] == ref["version"]
    assert ref["expected_key"] is None  # observed cohort cites present cells only
    if ref["row"] == "$":
        value = data[ref["column"]]
    else:
        matches = [r for r in data["rows"] if r["zip"] == ref["row"]]
        assert len(matches) == 1
        value = matches[0][ref["column"]]
    actual = (
        None if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    )
    assert actual == ref["value"]


def main():
    results, examples = [], []
    input_tokens = output_tokens = thinking = total_cost_micro = 0
    for result_path in sorted(EVIDENCE.rglob("result.json")):
        case = result_path.parent
        result, attempt, order = (
            load(case / name) for name in ("result.json", "attempt.json", "order.json")
        )
        terms = order["snapshot"]["quote"]["specification"]["terms"]
        if result["case"] == "P1":
            assert terms["category"] == "gym_app_or_yoga"
        else:
            assert terms["category"] == "gym_or_fitness_app"
        assert not order["ledger"] and order["free_corrections_used"] == 0
        assert (
            order["verification"]["passed"]
            if "passed" in order["verification"]
            else all(a["result"] == "PASS" for a in order["verification"]["assessments"])
        )
        refs = [
            r
            for key in ("candidate", "effective")
            if attempt[key]
            for r in attempt[key]["citations"] + attempt[key]["conflicting_evidence"]
        ]
        for ref in refs:
            exact_cell(case, order, ref)
        raw = attempt["raw_response"]
        usage = raw["usage"]
        assert raw["model"] == "claude-opus-5-5" and raw["stop_reason"] == "end_turn"
        assert usage["cache_creation_input_tokens"] == usage["cache_read_input_tokens"] == 0
        assert usage["service_tier"] == "standard" and usage["inference_geo"] == "global"
        cost = usage["input_tokens"] * 4 + usage["output_tokens"] * 20
        input_tokens += usage["input_tokens"]
        output_tokens += usage["output_tokens"]
        thinking += usage["output_tokens_details"]["thinking_tokens"]
        total_cost_micro += cost
        results.append(
            dict(
                case=result["case"],
                raw=result["raw"],
                effective=result["effective"],
                expected=result["expected"],
                references_checked=len(refs),
                estimated_cost_usd=cost / 1_000_000,
                latency_seconds=result["latency_seconds"],
            )
        )
        page = load(case / "events.json")
        for event in page["events"]:
            if event["type"] == "verdict":
                examples.append(
                    dict(
                        case=result["case"],
                        run_id=order["snapshot"]["quote"]["request_id"],
                        event=event,
                        evidence=load(case / "resolved-evidence.json"),
                    )
                )
    with sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT count(*),sum(actual_micro_usd),sum(status='RESERVED') FROM calls WHERE window_id=?",
            ("primary-semantic-followup-20261024",),
        ).fetchone()
    assert row == (len(results), total_cost_micro, 0)
    audit = dict(
        cases=results,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens_included_in_output=thinking,
        estimated_cost_usd=total_cost_micro / 1_000_000,
        ledger_reconciled=True,
        method="Independent hashlib/JSON/CSV inspection of saved bytes; no runtime resolver or model calls.",
    )
    with (EVIDENCE / "independent-audit.json").open("x", encoding="utf-8") as stream:
        json.dump(audit, stream, indent=2)
    with (ROOT / "docs/handoffs/primary-semantic-events.example.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(examples, stream, indent=2)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
