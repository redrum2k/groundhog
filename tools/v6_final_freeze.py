"""Freeze tested source/candidate/baselines/oracle, then allocate final dollars; no API call."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.agents.budget import ModelBudget
from app.improvement.catalog_memory import MEMORY_INSTRUCTION, MemoryDecision
from app.improvement.probes import implementation_digest
from v6_memory_pilot import experiences_from


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worlds", type=Path, required=True)
    parser.add_argument("--cycle", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    flags = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True, **flags).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo, text=True, **flags).strip()
    if dirty:
        raise SystemExit("Commit tested source before final freeze; worktree changes remain preserved")
    world_manifest = json.loads((args.worlds / "manifest.json").read_text())
    for filename, expected in world_manifest["files"].items():
        if sha(args.worlds / filename) != expected:
            raise SystemExit("Pre-reveal world/oracle capsule changed")
    database = (args.cycle / "development/orders.sqlite3").resolve()
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        def record(identifier):
            row = db.execute("SELECT body FROM im_records WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise ValueError("Exact saved improvement record missing")
            return json.loads(row[0])
        version = record(args.version)
        patch = record(version["patch_id"])
        approval = record(version["approval_id"])
        probe = record(version["probe_id"])
    source_hash = implementation_digest()
    if version["implementation_sha256"] != source_hash or approval["implementation_sha256"] != source_hash:
        raise SystemExit("Selected version is not approved on this exact source")
    if patch["mode"] != "ANTHROPIC" or patch["model"] != "claude-opus-5-5" or not probe["report"]["promotion_eligible"]:
        raise SystemExit("Selected candidate lacks genuine generation and eligible isolated probe")
    args.output.mkdir(parents=True, exist_ok=False)
    runtime_files = {}
    values = {"selected-proposal.json": patch["proposal"], "memory-experiences.json": experiences_from(args.cycle)}
    for name in ("visible-cases.json", "protocol.json"):
        values[name] = json.loads((args.worlds / name).read_text())
    for name, value in values.items():
        with (args.output / name).open("x") as handle:
            json.dump(value, handle, indent=2)
        runtime_files[name] = sha(args.output / name)
    snapshot_paths = [p for folder in ("backend/app", "frontend/components/run", "frontend/lib/run", "frontend/app/api/catalog")
                      for p in (repo / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx")]
    source_files = {p.relative_to(repo).as_posix(): sha(p) for p in snapshot_paths}
    capsule = {"kind": "V6_FROZEN_FINAL_RUN_CAPSULE", "created_at": datetime.now(UTC).isoformat(),
               "revision": revision, "implementation_sha256": source_hash, "source_files": source_files,
               "dependencies": {name: sha(repo / name) for name in ("backend/uv.lock", "frontend/package-lock.json")},
               "model": "claude-opus-5-5", "model_max_output_tokens": 4096, "model_timeout_seconds": 60,
               "model_retries": 0, "thinking": "provider adaptive default; unchanged quality setting",
               "memory_instruction": MEMORY_INSTRUCTION, "memory_output_schema": MemoryDecision.model_json_schema(),
               "runtime_files": runtime_files, "oracle_sha256": sha(args.worlds / "oracle.json"),
               "world_capsule_sha256": sha(args.worlds / "manifest.json"), "selected_version": version,
               "selected_patch": patch, "approval": approval,
               "probe_binding": {k: probe[k] for k in ("id", "candidate_sha256", "implementation_sha256", "report_sha256")},
               "arms": ["current_static", "competent_static", "functional_memory", "evolving_process"],
               "worlds": 12, "workflows": 48, "cutoff": "2026-10-24T10:10:00-07:00",
               "runner_sha256": sha(repo / "tools/v6_final_run.py"), "grader_sha256": sha(repo / "tools/v6_final_grade.py"),
               "forecast": {"measured_development_memory_cost_usd": 0.027540,
                            "expected_memory_decisions": 8, "expected_model_cost_usd": 0.22032,
                            "conservative_all_worlds_max_reservation_usd": 7,
                            "held_final_budget_usd": 10,
                            "note": "Measured pilot plus <=50k-character gateway context and4096output bound; every actual dispatch still reserves independently, no count ceiling"},
               "financial_authorization": "45USD aggregate including all past calls/retries; concurrency<=2; existing promotional credits only; no billing changes",
               "final_outcomes_seen": False}
    capsule_path = args.output / "run-capsule.json"
    with capsule_path.open("x") as handle:
        json.dump(capsule, handle, indent=2)
    plan_sha = sha(capsule_path)
    budget = ModelBudget.configured()
    budget.allocate_final(10, plan_sha256=plan_sha, reason="Frozen12world/4arm plan; measured memory pilot$0.027540, all-world conservative reservation forecast<7USD, hold10USD")
    print(json.dumps({"capsule": str(capsule_path), "plan_sha256": plan_sha, "source_sha256": source_hash,
                      "budget": budget.summary(), "application_requests_dispatched": 0}, indent=2))


if __name__ == "__main__":
    main()
