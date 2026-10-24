import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from evals.aggregate.execution import execute  # noqa: E402
from evals.aggregate.schema import load_inputs  # noqa: E402


@pytest.fixture(scope="module")
def inputs():
    root = ROOT / "evals/aggregate"
    return load_inputs(root / "cases.json", root / "expectations.development.json")


@pytest.fixture(scope="module")
def evidence(tmp_path_factory, inputs):
    root = tmp_path_factory.mktemp("aggregate-evidence")
    for case in inputs[0]:
        directory = root / case.id
        directory.mkdir()
        execute(case.recipe, directory, 30)
    return root
