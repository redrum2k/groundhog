import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.roi.pilot import export_pilot, summarize_observations
from evals.roi.scoring import load


def test_packet_is_unperformed_counterbalanced_and_fresh(tmp_path):
    root = tmp_path / "pilot"
    summary = export_pilot(root)
    assert summary["pairs"] == 12 and summary["tasks"] == 24
    assert summary["measured_minutes_saved"] is None
    assignments = load(root / "assignments.json")
    first = defaultdict(list)
    for task in assignments:
        if task["presentation_order"] == 1:
            first[task["category"]].append(task["condition"])
        assert "expected" not in task and task["status"] == "not_performed"
    assert all(set(conditions) == {"operator", "groundhog"} for conditions in first.values())
    assert Counter(a["participant_id"] for a in assignments) == {"P01": 8, "P02": 8, "P03": 8}
    assert (
        summarize_observations(load(root / "timing-form.json"))[
            "measured_minutes_saved_by_category"
        ]
        is None
    )
    assert load(root / "observations.json") == []
    assert len({p.read_bytes() for p in root.glob("participants/*/*/source-input.json")}) == 24


def observation(condition, seconds, category="repeat"):
    return dict(
        task_id=condition,
        pair_id="p",
        participant_id="P01",
        condition=condition,
        category=category,
        active_seconds=seconds,
        correction_seconds=1,
        provenance="internal_timed_pilot",
        started_at="2026-10-25T00:00:00Z",
        ended_at="2026-10-25T00:04:00Z",
    )


def test_only_actual_complete_category_pairs_have_measured_summaries():
    assert summarize_observations([observation("operator", 120)])["completed_pairs"] == 0
    result = summarize_observations([observation("operator", 120), observation("groundhog", 60)])
    assert result["participants"] == result["completed_pairs"] == 1
    assert result["measured_minutes_saved_by_category"] == {
        "repeat": dict(median=1, minimum=1, maximum=1, pairs=1)
    }
    other = summarize_observations(
        [observation("operator", 120), observation("groundhog", 60, "defect")]
    )
    assert other["measured_minutes_saved_by_category"] is None


@pytest.mark.parametrize("seconds", [-1, float("inf"), float("nan")])
def test_invalid_timing_is_not_savings(seconds):
    with pytest.raises(ValueError):
        summarize_observations([observation("operator", seconds)])
