"""Private subprocess entry. Receives only a test recipe and execution bounds."""

import json
import os
import random
import sys
from pathlib import Path

from evals.aggregate.schema import write_json


def main():
    directory = Path(sys.argv[1])
    payload = json.loads((directory / "task.json").read_bytes())
    os.umask(0o077)
    random.seed(payload["seed"])
    try:
        from evals.aggregate.execution import execute

        details = execute(payload["recipe"], directory, payload["max_steps"])
        operation = {"status": "completed", **details}
    except Exception as error:
        # Never serialize arbitrary exception text or raw provider responses.
        operation = {"status": "error", "error": type(error).__name__}
        if str(error) in {
            "case_step_limit",
            "runtime_job_failed",
            "offline_evaluation_forbids_network_or_provider",
        }:
            operation["reason"] = str(error)
        inputs = sorted(directory.glob("input-*.json"))
        if inputs:
            operation["last_boundary"] = json.loads(inputs[-1].read_bytes())["boundary"]
    write_json(directory / "operation.json", operation)
    return 0 if operation["status"] == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
