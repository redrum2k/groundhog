"""Greptile regressions: frozen source and actual downloaded JSON must be checked."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.audit_judge_journey import verify_download, verify_frozen_source


@pytest.mark.parametrize("mutation", [None, "count", "age_max", "duplicate", "source_id"])
def test_accepted_source_is_checked_independently_of_bundle(mutation):
    terms = dict(
        category="gym_or_fitness_app",
        geography="San Francisco",
        age_min=25,
        age_max=34,
        population="synthetic_adults",
        count_unit="unique_adults_per_zip",
        groups_disjoint=True,
    )
    source_id = "sf:prepared:request:gym_or_fitness_app"
    row = dict(zip="94110", area="Mission", count=123, status="released")
    frozen = dict(source_id=source_id, version=1, rows=[row.copy()], **terms)
    if mutation == "count":
        frozen["rows"][0]["count"] = 999
    elif mutation == "age_max":
        frozen["age_max"] = 44
    elif mutation == "duplicate":
        frozen["rows"].append(row.copy())
    elif mutation == "source_id":
        frozen["source_id"] = "unrelated"
    order = {"sources": [{"source_id": source_id, "version": 1, "artifact": {}}]}
    expected = {"94110": ("Mission", 123, "released")}
    if mutation:
        with pytest.raises(AssertionError):
            verify_frozen_source(order, terms, expected, lambda _: json.dumps(frozen).encode())
    else:
        verify_frozen_source(order, terms, expected, lambda _: json.dumps(frozen).encode())


@pytest.mark.parametrize("content", [None, b'{"rows":[]}', b'{"rows":[1]}'])
def test_json_download_must_exist_and_match_stored_bytes(tmp_path, content):
    path = tmp_path / "delivery.json"
    stored = b'{"rows":[1]}'
    if content is not None:
        path.write_bytes(content)
    if content == stored:
        assert verify_download(path, stored) == stored
    else:
        with pytest.raises(FileNotFoundError if content is None else AssertionError):
            verify_download(path, stored)
