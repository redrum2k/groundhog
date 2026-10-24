"""Export the backend contract without starting workers or making provider calls."""

import argparse
import json
from pathlib import Path

from app.main import create_app


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run --locked --directory backend python "
            "../tools/export_openapi.py --output ../docs/openapi.json"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(create_app(run_worker=False).openapi(), indent=2, sort_keys=True) + "\n"
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
