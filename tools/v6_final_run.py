"""Finite, independently supervised final workflows. Never opens the offline oracle."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.contracts.catalog_improvement import CatalogPatchProposal
from app.improvement.catalog_memory import FunctionalCatalogMemory
from app.improvement.catalog_probe import VisibleCatalogCase, run_visible_case
from app.improvement.probes import implementation_digest

ARMS = ("current_static", "competent_static", "functional_memory", "evolving_process")


def load_verified(root, capsule, name):
    raw = (root / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != capsule["runtime_files"][name]:
        raise ValueError(f"Frozen runtime file changed: {name}")
    return json.loads(raw)


def write_once(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--one", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()
    capsule_path = args.capsule.resolve()
    capsule = json.loads(capsule_path.read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != capsule["runner_sha256"]:
        raise SystemExit("Runner changed after freeze")
    root = capsule_path.parent
    deadline = datetime.fromisoformat(capsule["cutoff"])
    if implementation_digest() != capsule["implementation_sha256"]:
        raise SystemExit("Source changed after freeze; do not execute final worlds")
    if datetime.now(UTC) >= deadline:
        raise SystemExit("Original mission deadline reached")
    cases = load_verified(root, capsule, "visible-cases.json")
    proposal = CatalogPatchProposal.model_validate(load_verified(root, capsule, "selected-proposal.json"))
    memories = load_verified(root, capsule, "memory-experiences.json")
    args.output = args.output.resolve()
    if args.one:
        case = VisibleCatalogCase.model_validate(next(c for c in cases if c["id"] == args.case))
        memory = FunctionalCatalogMemory(memories, final_evaluation=True) if args.arm == "functional_memory" else None
        try:
            result = run_visible_case(case, arm=args.arm, proposal=proposal,
                                      memory_decider=memory, output=args.output / "workflow")
            result["frozen_implementation_sha256"] = implementation_digest()
            write_once(args.output / "result.json", result)
        finally:
            if memory:
                write_once(args.output / "memory-traces.json", memory.traces)
                memory.close()
        print(json.dumps({"case": case.id, "arm": args.arm, "status": "COMPLETE"}))
        return
    args.output.mkdir(parents=True, exist_ok=False)
    write_once(args.output / "run-start.json", {"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat(),
               "capsule_sha256": hashlib.sha256(capsule_path.read_bytes()).hexdigest(), "cutoff": deadline.isoformat()})
    outcomes = []
    for case in cases:
        for arm in ARMS:
            destination = args.output / case["id"] / arm
            destination.mkdir(parents=True, exist_ok=False)
            record = {"case_id": case["id"], "arm": arm, "started_at": datetime.now(UTC).isoformat(),
                      "status": "STARTED", "attempt": 1}
            write_once(destination / "started.json", record)
            remaining = (deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                record.update(status="NOT_RUN_DEADLINE")
            else:
                command = [sys.executable, str(Path(__file__).resolve()), "--capsule", str(capsule_path),
                           "--output", str(destination), "--one", "--case", case["id"], "--arm", arm]
                started = time.perf_counter()
                with (destination / "stdout.log").open("wb") as stdout, (destination / "stderr.log").open("wb") as stderr:
                    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    try:
                        code = child.wait(timeout=min(180, remaining))
                        record.update(status="COMPLETE" if code == 0 else "FAILED", exit_code=code)
                    except subprocess.TimeoutExpired:
                        if os.name == "nt":
                            subprocess.run(["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           stdin=subprocess.DEVNULL, timeout=15,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        else:
                            child.kill()
                        child.wait(timeout=15)
                        record.update(status="TIMEOUT_RETAINED", unknown_model_usage="Any unresolved ledger reservation remains charged")
                record["elapsed_seconds"] = time.perf_counter() - started
            record["finished_at"] = datetime.now(UTC).isoformat()
            write_once(destination / "completion.json", record)
            outcomes.append(record)
            # Progress is operational state; immutable per-arm results remain separate.
            (args.output / "progress.json").write_text(json.dumps({"pid": os.getpid(), "status": "RUNNING",
                "completed": len(outcomes), "total": len(cases) * len(ARMS), "last": record,
                "cutoff": deadline.isoformat()}, indent=2))
            print(json.dumps(record), flush=True)
    write_once(args.output / "run-complete.json", {"status": "FINISHED", "outcomes": outcomes,
               "finished_at": datetime.now(UTC).isoformat(), "no_oracle_loaded": True})
    (args.output / "progress.json").write_text(json.dumps({"status": "FINISHED", "completed": len(outcomes),
        "total": len(cases) * len(ARMS), "cutoff": deadline.isoformat()}, indent=2))


if __name__ == "__main__":
    main()
