import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.aggregate.execution import offline_guards
from evals.roi.execution import Arm
from evals.roi.lineage import check_lineage
from evals.roi.plan import ARMS, make_plan
from evals.roi.scoring import load, verify_order


@pytest.mark.parametrize("arm", ARMS)
def test_completed_paired_path_and_retained_operator_notes(tmp_path, arm):
    plan, _ = make_plan()
    system_root = os.environ.get("SystemRoot", "")
    with offline_guards(), patch.dict(os.environ, {"SystemRoot": system_root}):
        engine = Arm(tmp_path / arm, arm)
        setup = engine.run(plan["setup"][0])
        assert not setup["error"], setup["error"]
        assert setup["observed_disposition"] == "fulfilled"
        engine = Arm(tmp_path / arm, arm)
        later = engine.run(plan["cases"][0])
        assert not later["error"], later["error"]
        assert later["observed_disposition"] == "fulfilled"
        assert later["initial_source_reviews"] == (2 if arm == "no_learning" else 0)
        assert bool(later["reused_procedure"]) == (arm == "approved_learning")
        case_root = Path(later["artifact_directory"])
        verify_order(
            load(case_root / "order-0.json"),
            load(case_root / "justification-0.json"),
            plan["cases"][0],
            0,
            tmp_path / arm / "artifacts",
            engine.owner,
        )
        order = load(case_root / "order-0.json")
        order["snapshot"]["quote"]["payment_terms"]["amount_atomic"] = "500000"
        with pytest.raises(AssertionError):
            verify_order(
                order,
                load(case_root / "justification-0.json"),
                plan["cases"][0],
                0,
                tmp_path / arm / "artifacts",
                engine.owner,
            )
        if arm == "approved_learning":
            records = load(case_root / "learning-records.json")
            assert (
                check_lineage(plan["cases"][0], later, records, tmp_path / arm / "artifacts") == 2
            )
            changed = copy.deepcopy(records)
            changed["source_procedure"][0]["binding"]["authority"]["sha256"] = "0" * 64
            with pytest.raises(AssertionError):
                check_lineage(plan["cases"][0], later, changed, tmp_path / arm / "artifacts")
        doc = next(c for c in plan["cases"] if c["category"] == "documented")
        documented = Arm(tmp_path / (arm + "-documented"), arm).run(doc)
        assert not documented["error"] and documented["initial_source_reviews"] == 0
        assert documented["observed_disposition"] == "fulfilled"
