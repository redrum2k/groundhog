"""Freeze, supervise independent cases, audit evidence, and publish additive reports."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from evals.aggregate.results import metrics, normalize, render
from evals.aggregate.schema import ROOT, digest, verify_freeze, write_json


def provenance():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    paths = sorted(
        {
            *ROOT.glob("backend/app/**/*.py"),
            *ROOT.glob("evals/aggregate/**/*.py"),
            ROOT / "tools/aggregate_eval.py",
            ROOT / "tools/brokerage_acceptance.py",
            ROOT / "backend/uv.lock",
        }
    )
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    status = git("status", "--porcelain")
    return {
        "revision": git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "dirty_paths": status.splitlines(),
        "implementation_sha256": digest(manifest),
        "implementation_files": manifest,
        "fixture": "explicit-scope-v1",
        "audit": "primary-cells-v1",
        "audit_source_commit": "ef8c99afb9cf5f3b6928f505242f2d622fce2c3e",
        "audit_source_blob": "51acbf86a90ff8f1cc3e7397db3fd7776ad2fc68",
    }


def run_case(case, directory, config):
    directory.mkdir(mode=0o700)
    write_json(
        directory / "task.json",
        {"recipe": case.recipe, "max_steps": config.max_steps, "seed": config.seed},
    )
    env = {
        "PATH": os.defpath,
        "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "backend"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENABLE_PAID_MODELS": "false",
        "ENABLE_TESTNET_BROADCAST": "false",
        "PAYMENT_ADAPTER": "mock",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "evals.aggregate.worker", str(directory)],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=config.case_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "case_wall_clock_limit"}
    path = directory / "operation.json"
    if not path.exists():
        return {
            "status": "error",
            "error": "worker_exit_without_result",
            "exit_code": completed.returncode,
        }
    operation = json.loads(path.read_bytes())
    if completed.returncode and operation["status"] == "completed":
        return {
            "status": "error",
            "error": "worker_exit_after_result",
            "exit_code": completed.returncode,
        }
    return operation


def run(cases, expectations, config, output):
    output.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="aggregate-", dir=output)).resolve()
    private, public = directory / "private", directory / "artifacts"
    private.mkdir(mode=0o700)
    public.mkdir()
    source = provenance()
    plan = {
        "schema_version": "aggregate-plan-v1",
        "cases": [c.model_dump() for c in cases],
        "expectations": [e.model_dump() for e in expectations],
        "config": config.model_dump(),
        "provenance": source,
        "input_hashes": {
            "cases": digest([c.model_dump() for c in cases]),
            "expectations": digest([e.model_dump() for e in expectations]),
            "scoring": digest(config.model_dump()),
        },
    }
    frozen_hash = digest(plan)
    freeze = private / "frozen-plan.json"
    write_json(freeze, {"sha256": frozen_hash, "plan": plan})
    errors, results = [], []
    labels = {e.case_id: e for e in expectations}
    for case in cases:
        try:
            if verify_freeze(freeze)["sha256"] != frozen_hash:
                raise ValueError("plan_identity_changed")
            operation = run_case(case, private / case.id, config)
        except Exception as error:
            operation = {"status": "error", "error": type(error).__name__}
        results.append(normalize(case, labels.get(case.id), private / case.id, public, operation))
    try:
        if verify_freeze(freeze)["sha256"] != frozen_hash:
            raise ValueError("plan_identity_changed")
    except Exception:
        errors.append("Frozen input tampering detected; this run cannot be qualified.")
    if provenance()["implementation_sha256"] != source["implementation_sha256"]:
        errors.append("Implementation changed during execution; repeat in a new run directory.")
    report = {
        "schema_version": "aggregate-results-v1",
        "run_id": directory.name,
        "freeze_sha256": frozen_hash,
        "provenance": source,
        "config": config.model_dump(),
        "cases": results,
        "metrics": metrics(results),
        "errors": errors,
        "completed": sum(c["operation"]["status"] == "completed" for c in results),
        "mismatched": sum(bool(c["mismatches"]) for c in results),
        "incomplete": sum(c["outcome"] == "incomplete" for c in results),
        "qualification": "not_claimed",
        "usage": None,
        "cost": None,
        "dependencies": [
            "Rehan must independently review expectations and freeze development/held-out "
            "classification. Engineering fixtures are not gold or aggregate accuracy.",
            "Jeff's R3/R4 and published intake/Claude branch remain outside this reviewed "
            "baseline. Fixture compilation does not score intake.",
            "Raw model findings, paid usage and rate evidence are unavailable; "
            "no paid or RPC lane exists.",
            "Audit supports dataset present/null cells, missing top-level keys and "
            "frozen-coverage absent rows. Other reference kinds are unsupported/unscored.",
            "Synthetic evidence, deterministic clock/seed; runtime UUIDs remain intentionally "
            "nondeterministic. Private evidence includes initial rejected outputs.",
        ],
    }
    exit_code = 3 if errors or report["incomplete"] else 1 if report["mismatched"] else 0
    report["exit_code"] = exit_code
    report["evaluation_status"] = (
        "incomplete"
        if exit_code == 3
        else "completed_with_mismatches"
        if exit_code == 1
        else "completed"
    )
    write_json(directory / "results.json", report)
    (directory / "report.md").write_text(render(report), encoding="utf-8")
    return directory, report
