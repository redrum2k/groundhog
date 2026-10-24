"""Sanitized evidence/source export with SQLite snapshots, hashes and a strict archive cap."""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

SECRET = re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
LIMIT = 512_000_000


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--remote-sha", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    permitted_prior = Path("D:/Downloads/OBJECTION_V5_Results_20261024.zip").resolve()
    flags = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, **flags).strip()
    if revision != args.remote_sha:
        raise SystemExit("Delivery HEAD and verified remote SHA must agree")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True, **flags).strip():
        raise SystemExit("Tracked source changed after verification/commit")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True, **flags).strip()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root, **flags).decode().split("\0")
    args.output = args.output.resolve()
    args.archive = args.archive.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.archive.exists():
        raise SystemExit("Archive already exists; preserve it")
    files = {}
    sqlite_snapshots = []
    def copy(source, relative):
        source = source.resolve()
        if not source.is_relative_to(root) and source != permitted_prior:
            raise ValueError("Export source outside explicit repository/prior-artifact scope")
        if source.name == ".env" or (source.name.startswith(".env.") and source.name != ".env.example"):
            raise ValueError("Private environment file cannot be exported")
        if any(part in ("node_modules", ".venv", ".git", "__pycache__") for part in source.parts):
            raise ValueError("Dependency/cache export forbidden")
        target = args.output / relative
        if not target.resolve().is_relative_to(args.output):
            raise ValueError("Export member escapes output root")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == ".sqlite3":
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(target)) as snapshot:
                    original.backup(snapshot)
                    if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite evidence snapshot failed integrity check")
            sqlite_snapshots.append(relative)
        else:
            shutil.copy2(source, target)
        if SECRET.search(target.read_bytes()):
            raise ValueError(f"Secret pattern detected; export blocked in {relative}")
        files[relative.replace("\\", "/")] = {"sha256": digest(target), "bytes": target.stat().st_size}
    for name in tracked:
        if name:
            copy(root / name, "source/" + name)
    for directory, prefix in ((root / "backend/artifacts", "evidence/backend"), (root / "frontend/artifacts", "evidence/frontend")):
        for entry in sorted(directory.glob("v6-*")):
            members = [entry] if entry.is_file() else sorted(entry.rglob("*"))
            for source in members:
                if not source.is_file() or source.name.endswith(("-wal", "-shm", ".lock", ".pyc")):
                    continue
                copy(source, prefix + "/" + source.relative_to(directory).as_posix())
    prior = Path("D:/Downloads/OBJECTION_V5_Results_20261024.zip")
    if prior.is_file():
        copy(prior, "prior/" + prior.name)
    for source, target in (
        ("V6_RESULTS.md", "RESULTS.md"), ("V6_LIMITATIONS.md", "LIMITATIONS.md"),
        ("HANDOFF.md", "HANDOFF.md"), ("V6_API_CONTRACT.md", "API_CONTRACT.md"),
        ("V6_RUN_MANIFEST.json", "RUN_MANIFEST.json"),
        ("backend/artifacts/v6-final-reporting/metrics.csv", "METRICS.csv"),
    ):
        copy(root / source, target)
    patch = subprocess.check_output(["git", "diff", "--binary", "5c8dc72", revision], cwd=root, **flags)
    if SECRET.search(patch):
        raise ValueError("Secret pattern in delivery patch")
    (args.output / "SOURCE_PATCH.diff").write_bytes(patch)
    files["SOURCE_PATCH.diff"] = {"sha256": digest(args.output / "SOURCE_PATCH.diff"), "bytes": len(patch)}
    supervisors = [json.loads(path.read_text()) | {"directory": path.parent.name}
                   for path in (root / "backend/artifacts").glob("v6-live*/supervisor.json")]
    if any(s["status"] != "STOPPED" for s in supervisors):
        raise SystemExit("An owned app supervisor is not stopped")
    ledger_path = root / "backend/artifacts/v6-model-budget.sqlite3"
    with closing(sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True)) as db:
        reservations, active, known, committed = db.execute(
            "SELECT count(*),sum(status='RESERVED'),sum(coalesce(actual_micro_usd,0)),"
            "sum(coalesce(actual_micro_usd,reserved_micro_usd)) FROM calls").fetchone()
        rows = db.execute("SELECT status,count(*) FROM calls GROUP BY status").fetchall()
    if active or committed > 45_000_000:
        raise SystemExit("Unsettled active calls or expenditure overrun prevents completion")
    capsule = root / "backend/artifacts/v6-final-capsule/run-capsule.json"
    frozen = json.loads(capsule.read_text())
    from app.improvement.probes import implementation_digest
    if implementation_digest() != frozen["implementation_sha256"]:
        raise SystemExit("Scientific backend changed; do not relabel frozen results")
    score = json.loads((root / "backend/artifacts/v6-final-score/score.json").read_text())
    start = "2026-10-24T02:10:00-07:00"
    cutoff = datetime.fromisoformat("2026-10-24T10:10:00-07:00")
    if datetime.now(UTC) >= cutoff:
        raise SystemExit("Original deadline reached before export verification")
    manifest = {
        "status": "COMPLETE", "created_at": datetime.now(UTC).isoformat(), "original_start": start,
        "original_cutoff": cutoff.isoformat(), "clock_reset": False,
        "qualification": "ADAPTATION_QUALIFIED", "operating_benefit_qualified": score["operating_benefit_qualified"],
        "second_cycle": "NOT_QUALIFIED_NOT_RUN", "all_48_final_cells_correct": score["all_independently_correct"],
        "branch": branch, "delivery_revision": revision, "verified_remote_sha": args.remote_sha,
        "frozen_scientific_revision": frozen["revision"], "frozen_implementation_sha256": frozen["implementation_sha256"],
        "frozen_run_capsule_sha256": digest(capsule),
        "budget": {"ceiling_usd": 45, "request_count_ceiling": None, "concurrency_ceiling": 2,
                   "reservations": reservations, "statuses": dict(rows), "active": active,
                   "estimated_known_usage_usd": known / 1000000,
                   "conservative_committed_usd": committed / 1000000},
        "owned_supervisors": supervisors, "no_billing_or_autorecharge_changes": True,
        "no_live_settlement_or_deployment": True, "no_automatic_successor": True,
        "sqlite_evidence_snapshots": sqlite_snapshots,
        "source_and_oracle_separated": "source/ contains application code; final oracle is offline evidence/ only",
        "files": files,
    }
    (args.output / "DELIVERY_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    (args.output / "START_HERE.md").write_text(
        "# OBJECTION V6\n\nRead RESULTS.md first, then LIMITATIONS.md and HANDOFF.md.\n\n"
        "Bounded adaptation demonstrated; no recurring-action advantage over the strongest baseline.\n"
        "All48 final checks passed. All financial outcomes are mock.\n\n"
        f"Delivery/source and verified remote SHA: {revision}\n"
        f"Branch: {branch}\n\n"
        "METRICS.csv contains stage/action/token/cost measurements. Raw failures, model responses,\n"
        "probes,48 workflows, browser screenshots/PDFs and a separate offline oracle are in evidence/.\n"
        "source/ and SOURCE_PATCH.diff preserve the exact implementation. No credentials/dependencies\n"
        "are included. DELIVERY_MANIFEST.json hashes every copied source/evidence member.\n"
        "The original V5 archive is preserved under prior/ when available.\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(args.output).as_posix())
    if args.archive.stat().st_size >= LIMIT:
        raise SystemExit("Archive exceeds512000000 bytes; preserve it for explicit corrective packaging")
    with zipfile.ZipFile(args.archive) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive CRC verification failed")
        for name, expected in files.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected["sha256"]:
                raise ValueError(f"Archive member hash mismatch: {name}")
    report = {"status": "VERIFIED", "archive": str(args.archive), "bytes": args.archive.stat().st_size,
              "sha256": digest(args.archive), "members": len(files) + 2, "source_revision": revision,
              "remote_sha": args.remote_sha, "delivery_manifest_sha256": digest(args.output / "DELIVERY_MANIFEST.json"),
              "completed_at": datetime.now(UTC).isoformat()}
    with args.archive.with_suffix(".verification.json").open("x") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
