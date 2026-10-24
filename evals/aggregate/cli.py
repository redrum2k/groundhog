"""Small noninteractive CLI; validation/listing never import runtime execution."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from evals.aggregate.schema import Config, load_inputs

HERE = Path(__file__).parent


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate aggregate brokerage offline with explicit mock funding.",
        epilog="Examples: aggregate_eval.py list; aggregate_eval.py validate; "
        "aggregate_eval.py run --case D01 --output /private/tmp/aggregate-evaluation. "
        "Exit: 0 completed, 1 quality mismatch, 2 invalid input, 3 incomplete/operational.",
    )
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "validate", "run"):
        sub = subs.add_parser(
            name,
            epilog=f"Example: aggregate_eval.py {name}"
            + (" --output /private/tmp/aggregate-evaluation" if name == "run" else ""),
        )
        sub.add_argument("--cases", type=Path, default=HERE / "cases.json")
        sub.add_argument(
            "--expectations",
            type=Path,
            default=HERE / "expectations.development.json",
            help="Strict expectation JSON; use --unscored to report without labels.",
        )
        sub.add_argument("--unscored", action="store_true")
        sub.add_argument(
            "--case", action="append", default=[], help="Exact case ID; repeat to select."
        )
        if name == "run":
            sub.add_argument(
                "--output", type=Path, required=True, help="Parent of a fresh run directory."
            )
            sub.add_argument(
                "--case-seconds", type=float, default=20, help="Hard child timeout (0,120]."
            )
            sub.add_argument("--max-steps", type=int, default=30)
            sub.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        cases, expectations = load_inputs(
            args.cases, None if args.unscored else args.expectations, args.case
        )
        config = (
            Config(case_seconds=args.case_seconds, max_steps=args.max_steps, seed=args.seed)
            if args.command == "run"
            else None
        )
        if args.command == "run" and args.output.exists() and not args.output.is_dir():
            raise ValueError("--output must be a directory, not an existing file")
    except (ValueError, OSError) as error:
        from pydantic import ValidationError

        if isinstance(error, ValidationError):
            detail = "; ".join(
                ".".join(map(str, item["loc"])) + ": " + item["type"]
                for item in error.errors(include_input=False, include_url=False)[:5]
            )
        elif isinstance(error, OSError):
            detail = f"cannot read input file ({type(error).__name__})"
        else:
            # load_inputs raises only fixed, value-free diagnostics.
            detail = str(error)
        print(
            f"Invalid input: {detail}. "
            "Example: aggregate_eval.py validate --cases cases.json --expectations labels.json",
            file=sys.stderr,
        )
        return 2
    if args.command != "run":
        print(
            json.dumps(
                {
                    "valid": True,
                    "cases": [c.model_dump() for c in cases],
                    "expectation_cases": len(expectations),
                    "runtime_work": False,
                },
                indent=2,
            )
        )
        return 0
    from evals.aggregate.runner import run

    try:
        directory, report = run(cases, expectations, config, args.output)
    except (OSError, subprocess.SubprocessError) as error:
        print(
            f"Evaluation could not complete report storage or revision inspection "
            f"({type(error).__name__}); choose a writable --output directory "
            "inside this checkout's environment. Existing runs are preserved.",
            file=sys.stderr,
        )
        return 3
    print(
        json.dumps(
            {
                "run_directory": str(directory),
                "report": str(directory / "report.md"),
                "results": str(directory / "results.json"),
                "exit_code": report["exit_code"],
            }
        )
    )
    return report["exit_code"]
