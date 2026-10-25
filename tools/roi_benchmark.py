"""Frozen offline ROI lab. No live lane is implied by credentials or historical trials."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.roi.plan import ARMS, digest, freeze, save  # noqa: E402


def git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).strip()


def execute(directory):
    plan = json.loads((directory / "inputs.json").read_text(encoding="utf-8"))
    capsule = json.loads((directory / "capsule.json").read_text(encoding="utf-8"))
    if (
        digest(plan) != capsule["plan"]["input_sha256"]
        or digest(capsule["plan"]) != capsule["sha256"]
    ):
        raise ValueError("Frozen input/capsule changed")
    if git("rev-parse", "HEAD") != plan["source_commit"] or git(
        "status", "--porcelain", "--untracked-files=no"
    ):
        raise ValueError("Commit implementation before freezing/running the workload")
    started = time.monotonic()
    technical = []
    for arm in ARMS:
        for stream in dict.fromkeys(c["stream_id"] for c in plan["setup"] + plan["cases"]):
            cases = [c for c in plan["setup"] + plan["cases"] if c["stream_id"] == stream]
            chunks = [(0, 11), (11, len(cases))] if stream == "recurring" else [(0, len(cases))]
            for start, stop in chunks:
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "worker",
                    "--output",
                    str(directory),
                    "--arm",
                    arm,
                    "--stream",
                    stream,
                    "--start",
                    str(start),
                    "--stop",
                    str(stop),
                ]
                result = subprocess.run(
                    command,
                    cwd=ROOT / "backend",
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=max(1, plan["max_seconds"] - (time.monotonic() - started)),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                technical.append(
                    dict(
                        arm=arm,
                        stream=stream,
                        start=start,
                        stop=stop,
                        exit_code=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                    )
                )
                print(f"{arm} / {stream} [{start}:{stop}]: exit {result.returncode}", flush=True)
                # Preserve failures and keep other paired cases in the denominator.
    save(
        directory / "technical-attempt.json",
        dict(
            attempt=1,
            elapsed_seconds=time.monotonic() - started,
            processes=technical,
            cleanup=(
                "All bounded child processes joined; no services, remote resources "
                "or paid clients created"
            ),
        ),
    )
    from evals.roi.scoring import score

    report = score(directory)
    print(
        json.dumps({"quality_gate": report["quality_gate"], "summary": report["summary"]}, indent=2)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("freeze", "run", "worker", "score", "report", "pilot", "audit-lineage")
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--stream")
    parser.add_argument("--report-name", default="report.html")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=1000)
    args = parser.parse_args()
    directory = args.output.resolve()
    if not directory.is_relative_to(ROOT / ".local"):
        raise ValueError("Outputs must remain in this worktree's private .local directory")
    if args.action == "freeze":
        if git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Commit first; a capsule must name its tested implementation")
        print(json.dumps(freeze(directory, git("rev-parse", "HEAD")), indent=2))
    elif args.action == "run":
        execute(directory)
    elif args.action == "worker":
        from evals.roi.execution import worker

        worker(directory, args.arm, args.stream, args.start, args.stop)
    elif args.action == "score":
        from evals.roi.scoring import score

        print(json.dumps(score(directory)["summary"], indent=2))
    elif args.action == "report":
        from evals.roi.report import render

        print(
            json.dumps(
                {
                    "quality_gate": render(directory, args.report_name)["quality_gate"],
                    "report": str(directory / args.report_name),
                }
            )
        )
    elif args.action == "pilot":
        from evals.roi.pilot import export_pilot

        print(json.dumps(export_pilot(directory / "pilot")))
    else:
        from evals.roi.lineage import audit

        print(json.dumps(audit(directory)))


if __name__ == "__main__":
    main()
