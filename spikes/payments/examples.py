"""Run all three synthetic journeys in separate CLI processes with an empty environment.

Usage from root: backend/.venv/bin/python spikes/payments/examples.py
Journals use a new temporary directory. No RPC URL or user credential is loaded.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    runner = Path(__file__).with_name("run.py")
    with tempfile.TemporaryDirectory(prefix="base-payment-examples-") as directory:
        for identifier, terminal in (
            ("capture-a", "capture"),
            ("void-b", "void"),
            ("expiry-c", "reclaim"),
        ):
            common = [
                "--offline",
                "--payment-id",
                identifier,
                "--journal",
                str(Path(directory) / f"{identifier}.sqlite3"),
            ]
            sequence = [
                ("preflight", []),
                ("prepare", ["--save-fixture"]),
                ("fund", ["--dry-run"]),
                ("fund", ["--simulate"]),
                ("status", []),
                ("reconcile", []),
                (
                    terminal,
                    ["--simulate", "--offline-time", "4600"]
                    if terminal == "reclaim"
                    else ["--simulate"],
                ),
                ("reconcile", ["--offline-time", "4600"] if terminal == "reclaim" else []),
                ("status", []),
            ]
            for command, flags in sequence:
                result = subprocess.run(
                    [sys.executable, str(runner), command, *common, *flags],
                    env={"PATH": os.defpath},
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=True,
                )
                output = json.loads(result.stdout)
                print(
                    json.dumps(
                        {
                            "evidence": "OFFLINE ONLY; no real receipt",
                            "payment_id": identifier,
                            "command": command,
                            "state": output.get("state", "preflight passed"),
                        }
                    )
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
