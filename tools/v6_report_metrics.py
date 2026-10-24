"""Supplement frozen grading with actual ledger costs and deduplicated PDF inspection files."""
import argparse
import base64
import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    score = json.loads(args.score.read_text())
    with closing(sqlite3.connect(args.ledger.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        calls = {r["id"]: dict(r) for r in db.execute("SELECT * FROM calls")}
    rows, pdfs = [], {}
    for graded in score["rows"]:
        result = json.loads((args.runs / graded["case_id"] / graded["arm"] / "result.json").read_text())
        ids = [t["ledger_call_id"] for t in result["memory_decisions"] if t.get("ledger_call_id")]
        billed = [calls[identifier] for identifier in ids]
        usage = [json.loads(c["usage_json"]) for c in billed if c["usage_json"]]
        row = {**graded, "model_attempts": len(billed),
               "model_input_tokens": sum(int(u.get("input_tokens", 0)) for u in usage),
               "model_output_tokens": sum(int(u.get("output_tokens", 0)) for u in usage),
               "model_thinking_tokens_included_in_output": sum(int((u.get("output_tokens_details") or {}).get("thinking_tokens", 0)) for u in usage),
               "model_cache_creation_tokens": sum(int(u.get("cache_creation_input_tokens", 0)) for u in usage),
               "model_cache_read_tokens": sum(int(u.get("cache_read_input_tokens", 0)) for u in usage),
               "model_known_cost_usd": sum(c["actual_micro_usd"] or 0 for c in billed) / 1000000,
               "model_conservative_committed_usd": sum(c["actual_micro_usd"] if c["actual_micro_usd"] is not None else c["reserved_micro_usd"] for c in billed) / 1000000,
               "model_latency_seconds": sum(t["latency_seconds"] for t in result["memory_decisions"]),
               "pending_obligation_details": result["pending_obligation_details"]}
        rows.append(row)
        for delivery in result["order"]["order"]["deliveries"]:
            digest = delivery["pdf"]["sha256"]
            raw = base64.b64decode(result["artifact_bytes_by_sha256"][digest])
            assert hashlib.sha256(raw).hexdigest() == digest
            if digest not in pdfs:
                folder = args.output / "pdf-inspection"
                folder.mkdir(exist_ok=True)
                target = folder / f"{graded['case_id']}-{digest[:12]}.pdf"
                target.write_bytes(raw)
                document = pdfium.PdfDocument(raw)
                images = []
                for index in range(len(document)):
                    image = target.with_suffix(f".page-{index + 1}.png")
                    document[index].render(scale=1.25).to_pil().save(image)
                    images.append(image.name)
                document.close()
                pdfs[digest] = {"case_id": graded["case_id"], "file": target.name, "images": images, "arms": []}
            pdfs[digest]["arms"].append(graded["arm"])
    totals = {}
    for arm in score["summary"]:
        values = [r for r in rows if r["arm"] == arm]
        totals[arm] = {key: sum(r[key] for r in values) for key in (
            "model_attempts", "model_input_tokens", "model_output_tokens", "model_thinking_tokens_included_in_output",
            "model_known_cost_usd", "model_conservative_committed_usd", "model_latency_seconds")}
    result = {"frozen_score_sha256": hashlib.sha256(args.score.read_bytes()).hexdigest(), "rows": rows,
              "per_arm_model_usage": totals, "unique_delivered_pdfs": pdfs,
              "note": "Supplementary descriptive accounting only; frozen oracle, grader and outcome decisions unchanged. Thinking is part of output_tokens, not extra cost."}
    (args.output / "metrics.json").write_text(json.dumps(result, indent=2))
    fields = list(rows[0])
    with (args.output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)
    print(json.dumps({"per_arm_model_usage": totals, "unique_delivered_pdfs": len(pdfs), "pages_to_inspect": [p for item in pdfs.values() for p in item["images"]]}, indent=2))


if __name__ == "__main__":
    main()
