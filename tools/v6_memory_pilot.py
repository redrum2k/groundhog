"""One development-only functional-memory pilot, charged to the shared ledger."""

import argparse
import json
from pathlib import Path

from app.agents.budget import ModelBudget
from app.improvement.catalog_memory import FunctionalCatalogMemory
from app.improvement.catalog_probe import development_cases, run_visible_case


def experiences_from(cycle_root):
    records = json.loads((cycle_root / "improvement-records.json").read_text())["records"]
    incident = next(r for r in records if r["kind"] == "catalog_incident")
    outcome = json.loads((cycle_root / "development-static.json").read_text())
    return [{
        "id": incident["id"], "corpus_id": incident["corpus_id"],
        "observed_blockers": [{"reason_code": a["reason_code"], "explanation": a["explanation"],
                               "source_quotes": [c["quote"] for c in a["citations"]]}
                              for a in incident["data"]["blockers"]],
        "observed_amendments": [{"classification": a["classification"], "actor": a["actor"],
                                 "reason_codes": [c["reason_code"] for c in a["assessment"]]}
                                for a in outcome["order"]["order"]["amendments"]],
        "observed_result": {key: outcome[key] for key in ("order_state", "payment_state", "financial_effects")},
        "observed_manual_evidence_uploads": outcome["company_actions"]["manual_evidence_acquisition"],
        "limitations": "One synthetic development case, simulated clock and finance; no measured labor time or universal success claim",
    }]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    memories = experiences_from(args.cycle)
    (args.output / "experiences.json").write_text(json.dumps(memories, indent=2))
    decision = FunctionalCatalogMemory(memories)
    before = ModelBudget.configured().summary()
    try:
        result = run_visible_case(development_cases("storage-2026")[0], arm="functional_memory",
                                  memory_decider=decision, output=args.output / "workflow")
        (args.output / "workflow.json").write_text(json.dumps(result, indent=2))
    finally:
        (args.output / "model-traces.json").write_text(json.dumps(decision.traces, indent=2))
        decision.close()
    after = ModelBudget.configured().summary()
    summary = {"mode": "real_application_model / development_only / mock_finance", "before": before, "after": after,
               "decisions": len(decision.traces), "statuses": [t["status"] for t in decision.traces],
               "operationally_closed": result["operationally_closed"], "company_actions": result["company_actions"]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
