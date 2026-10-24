"""Real application proposals from persisted development incidents; no final truth."""

import argparse
import json
from pathlib import Path

from app.agents.budget import ModelBudget
from app.contracts.catalog_improvement import CatalogImprovementCommand
from app.improvement.catalog import BASE, CatalogProcedures
from app.improvement.catalog_probe import ProbeClock, development_cases, run_visible_case
from app.improvement.probes import implementation_digest
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("propose", "probe"), required=True)
    parser.add_argument("--command-key", default="v6-real-cycle-1")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    initial = root / "development-static.json"
    if not initial.exists():
        if args.phase != "propose":
            raise SystemExit("A persisted proposal development run is required")
        if (root / "development/orders.sqlite3").exists():
            raise SystemExit("Partial development store exists; inspect rather than overwrite it")
        trace = run_visible_case(development_cases("storage-2026")[0], arm="current_static",
                                 output=root / "development")
        initial.write_text(json.dumps(trace, indent=2))
    clock = ProbeClock()
    clock.advance(121)
    service = CatalogService(CatalogRepository(root / "development/orders.sqlite3"),
                              root / "development/artifacts", clock)
    procedures = CatalogProcedures(service)
    before = procedures.view("storage-2026")
    if args.phase == "propose":
        incidents = [r for r in before.records if r.kind == "catalog_incident"]
        if not incidents:
            raise SystemExit("No real persisted incident; no model request was made")
        command = CatalogImprovementCommand(
            verb="propose", corpus_id="storage-2026", idempotency_key=args.command_key,
            expected_active_version=BASE, incident_ids=(incidents[0].id,),
            reason="Observed synthetic provider evidence-acquisition action after unreadable catalog fact",
        )
        result = procedures.propose(command, actor="provider:local-worker")
        previous = root / "proposal-result.json"
        if previous.exists():
            prior = json.loads(previous.read_text())
            (root / f"proposal-result-{prior['job_id']}.json").write_text(json.dumps(prior, indent=2))
        (root / "proposal-result.json").write_text(result.model_dump_json(indent=2))
        (root / f"proposal-result-{result.job_id}.json").write_text(result.model_dump_json(indent=2))
    else:
        saved = json.loads((root / "proposal-result.json").read_text())
        if saved["status"] != "COMPLETE" or not saved["patch_ids"]:
            raise SystemExit("No validated model patch is available for probing")
        outcomes = []
        for patch_id in saved["patch_ids"]:
            result = procedures.probe(CatalogImprovementCommand(
                verb="probe", corpus_id="storage-2026", idempotency_key=f"probe:{patch_id}:{implementation_digest()}",
                expected_active_version=BASE, patch_id=patch_id,
                reason="Isolated actual application-command baseline and boundary comparisons",
            ), actor="provider:local-worker")
            outcomes.append(result.model_dump(mode="json"))
        (root / "probe-results.json").write_text(json.dumps(outcomes, indent=2))
    view = procedures.view("storage-2026")
    (root / "improvement-records.json").write_text(view.model_dump_json(indent=2))
    report = {"phase": args.phase, "status": result.status,
              "patch_ids": result.patch_ids, "probe_id": result.probe_id,
              "reason": result.reason, "source_sha256": implementation_digest(),
              "budget": ModelBudget.configured().summary(), "output": str(root)}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
