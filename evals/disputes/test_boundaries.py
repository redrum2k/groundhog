"""Evaluator boundary checks.

uv run --locked --directory backend pytest ../evals/disputes
With DISPUTE_DATASET=<extracted bundle> set, the dataset-dependent tests run too.
"""

import json
import os
import re

import pytest
from arms import Evolving, Memory, Static, train_set
from build_memory import build
from common import (
    CASES,
    EXPECTED,
    LEAKY_CASE_FIELDS,
    REPO,
    Dataset,
    assert_safe_view,
    sha256_file,
    sim_view,
)

DATASET = os.environ.get("DISPUTE_DATASET")
needs_dataset = pytest.mark.skipif(
    not DATASET, reason="set DISPUTE_DATASET to the extracted bundle"
)


def holdout_views():
    manifest = json.loads((CASES / "holdout" / "MANIFEST.json").read_text())
    return manifest, [
        json.loads((CASES / "holdout" / i["case_id"] / "view.json").read_text())
        for i in manifest["index"]
    ]


def test_runtime_never_reads_evaluator_files():
    pattern = re.compile(r"evals[/\\.]|holdout_labels|hf_review")
    for path in (REPO / "backend" / "app").rglob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), path


def test_holdout_is_sealed_and_label_free():
    manifest, views = holdout_views()
    assert 60 <= manifest["cases"] <= 120
    assert sha256_file(EXPECTED / "holdout_labels.json") == manifest["labels_sha256"]
    labels = json.loads((EXPECTED / "holdout_labels.json").read_text())
    mechanisms = {v["mechanism"] for v in labels.values()}
    for item, view in zip(manifest["index"], views, strict=True):
        assert sha256_file(CASES / "holdout" / item["case_id"] / "view.json") == item["view_sha256"]
        assert_safe_view(view)
        blob = json.dumps(view)
        assert not any(m in blob for m in mechanisms), view["case_id"]
        for key in ("acceptable_primary", "required_citations", "settlement", "forbidden_actions"):
            assert f'"{key}"' not in blob


def test_holdout_validator_agrees_with_design():
    diagnostics = json.loads((EXPECTED / "holdout_diagnostics.json").read_text())
    assert all(d["validator_agrees"] for d in diagnostics)


def test_hf_views_drop_keyword_remedies_and_replies():
    path = CASES / "hf_views.jsonl"
    if not path.exists():
        pytest.skip("run hf_stress.py first")
    for line in path.read_text().splitlines():
        view = json.loads(line)
        assert view["agreement"] is None and view["checks"] == []
        # Only the reporter's opening text is received; no reply turns or keyword remedy.
        assert set(view) == {
            "case_id",
            "domain",
            "agreement",
            "checks",
            "source_ok",
            "messages",
            "complaint_target",
            "correction_used",
            "questions_asked",
            "max_questions",
        }
        assert len(view["messages"]) == 1 and '"maps_to_family"' not in line


@needs_dataset
def test_memory_is_train_only_and_policy_translated():
    ds = Dataset(DATASET)
    contrastive, convergent, lessons = build(ds)
    dev = {c["case_id"] for c in ds.dev}
    blob = json.dumps([contrastive, convergent, lessons])
    assert not [i for i in dev if f'"{i}"' in blob]
    assert len(contrastive) == len(ds.train)
    for lesson in lessons:
        if lesson["source_family"] in ("exclude_with_credit", "sla_credit"):
            assert lesson["actions"] == ["human_review"]


@needs_dataset
def test_decision_views_hide_labels_and_future_turns():
    ds = Dataset(DATASET)
    for case in ds.dev:
        view = sim_view(case)
        assert_safe_view(view)
        assert len(view["messages"]) == 1
        blob = json.dumps(view)
        for key in LEAKY_CASE_FIELDS:
            assert f'"{key}"' not in blob


@needs_dataset
def test_arms_decide_without_labels():
    ds = Dataset(DATASET)
    views, labels = train_set(ds)
    _, hold = holdout_views()
    for arm in (Static(), Memory(), Evolving()):
        arm.fit(views, labels)
        for view in hold[:10] + [sim_view(c) for c in ds.dev[:10]]:
            out = arm.decide(view)
            assert out["financial_action"] is None and out["model_calls"] == 0
