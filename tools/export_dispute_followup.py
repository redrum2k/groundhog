"""Export committed source plus synthetic evidence, with member hashes and no credentials."""

import hashlib
import json
import sqlite3
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "backend/artifacts/dispute-followup"
DESTINATION = Path("D:/Downloads/OBJECTION_Dispute_Followup_Results_20261024.zip")
LEDGER = Path("D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3")


def git(*arguments):
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )


def main():
    if git("status", "--porcelain").strip():
        raise RuntimeError("Only export a clean tested feature commit")
    branch = git("branch", "--show-current").decode().strip()
    if branch != "feature/broker-dispute-assessment-20261024":
        raise RuntimeError("Wrong source branch")
    if DESTINATION.exists():
        raise RuntimeError("Never overwrite a prior results archive")
    snapshot = EVIDENCE / "shared-ledger-snapshot.sqlite3"
    if snapshot.exists():
        raise RuntimeError("Ledger snapshot already exists")
    with sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True) as source:
        if source.execute("SELECT count(*) FROM calls WHERE status='RESERVED'").fetchone()[0]:
            raise RuntimeError("Calls are still active")
        with sqlite3.connect(snapshot) as destination:
            source.backup(destination)
    commit = git("rev-parse", "HEAD").decode().strip()
    remote = git("ls-remote", "origin", f"refs/heads/{branch}").decode().split()[0]
    if remote != commit:
        raise RuntimeError("Remote feature branch does not match tested source")
    receipt = {
        "commit": commit,
        "remote_commit": remote,
        "branch": branch,
        "base": "c2f561956fc5189688e70918967ef5c9eb87f5fe",
        "exported_at": datetime.now(UTC).isoformat(),
        "feature_enabled": False,
    }
    manifest = []
    with zipfile.ZipFile(DESTINATION, "x", compression=zipfile.ZIP_DEFLATED) as archive:

        def add(name, data):
            archive.writestr(name, data)
            manifest.append(
                {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            )

        for raw_name in git("ls-files", "-z").decode().split("\0"):
            if not raw_name:
                continue
            path = ROOT / raw_name
            if any(part.startswith(".env") for part in path.parts):
                continue
            add("source/" + raw_name, path.read_bytes())
        for path in sorted(EVIDENCE.rglob("*")):
            if path.is_file() and path.suffix not in {".wal", ".shm"}:
                add("evidence/" + path.relative_to(EVIDENCE).as_posix(), path.read_bytes())
        add("delivery-receipt.json", json.dumps(receipt, indent=2).encode())
        add("feature.patch", git("diff", "c2f5619...HEAD", "--"))
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(DESTINATION) as archive:
        for member in manifest:
            if hashlib.sha256(archive.read(member["path"])).hexdigest() != member["sha256"]:
                raise RuntimeError("Archive member verification failed")
    verification = {
        **receipt,
        "archive": str(DESTINATION),
        "members_verified": len(manifest),
        "bytes": DESTINATION.stat().st_size,
        "sha256": hashlib.sha256(DESTINATION.read_bytes()).hexdigest(),
    }
    with DESTINATION.with_suffix(".verification.json").open("x", encoding="utf-8") as stream:
        json.dump(verification, stream, indent=2)
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
