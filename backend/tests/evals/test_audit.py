import hashlib
import json

import pytest
from evals.aggregate.audit import audit_artifacts, exact_cell


def artifact(root, content, media="application/json"):
    raw = json.dumps(content).encode() if not isinstance(content, bytes) else content
    sha = hashlib.sha256(raw).hexdigest()
    (root / sha).write_bytes(raw)
    return {"artifact_id": sha[:24], "sha256": sha, "storage_key": sha, "media_type": media}


def ref(a, **kw):
    return {
        "kind": "dataset",
        "artifact_id": a["artifact_id"],
        "sha256": a["sha256"],
        "source_id": "source",
        "version": 1,
        "row": "$",
        "column": "value",
        "value": None,
        "expected_key": None,
        "coverage_sha256": None,
        **kw,
    }


@pytest.mark.parametrize(
    "value,text", [(None, None), (True, "true"), (False, "false"), (25, "25"), ("Gym", "Gym")]
)
def test_published_present_cell_compatibility(tmp_path, value, text):
    # Same explicit JSON scalar vectors as Jeff's attributed present-cell algorithm.
    a = artifact(tmp_path, {"source_id": "source", "version": 1, "value": value})
    assert exact_cell(tmp_path, [a], ref(a, value=text))["status"] == "valid"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"sha256": "0" * 64}, "reference_hash_mismatch"),
        ({"version": 2}, "source_version_mismatch"),
        ({"source_id": "other"}, "source_identity_mismatch"),
        ({"value": "false"}, "cell_value_mismatch"),
    ],
)
def test_invalid_cell_identity_or_value(tmp_path, change, reason):
    a = artifact(tmp_path, {"source_id": "source", "version": 1, "value": True})
    result = exact_cell(tmp_path, [a], ref(a, value="true") | change)
    assert result == {"status": "invalid", "reason": reason}


def test_tampered_bytes_even_with_resolving_runtime_claim(tmp_path):
    a = artifact(tmp_path, {"source_id": "source", "version": 1, "value": True})
    (tmp_path / a["storage_key"]).write_text("{}")
    assert exact_cell(tmp_path, [a], ref(a, value="true"))["reason"] == "artifact_hash_mismatch"


def test_csv_version_null_and_private_unsafe_count(tmp_path):
    a = artifact(tmp_path, b"zip,area,count,status\n94129,SF,,suppressed\n", "text/csv")
    citation = ref(a, source_id="delivery", row="94129", column="count")
    deliveries = [{"version": 1, "csv": a}]
    assert exact_cell(tmp_path, [a], citation, deliveries=deliveries) == {
        "status": "valid",
        "reason": "null_cell",
    }
    assert (
        exact_cell(tmp_path, [a], citation | {"version": 2}, deliveries=deliveries)["reason"]
        == "delivery_version_mismatch"
    )
    b = artifact(tmp_path, b"zip,area,count,status\n94129,SF,37,suppressed\n", "text/csv")
    result = exact_cell(
        tmp_path,
        [b],
        ref(b, source_id="delivery", row="94129", column="count"),
        deliveries=[{"version": 1, "csv": b}],
    )
    assert result == {"status": "invalid", "reason": "unsafe_nonreleased_count"}
    assert "37" not in json.dumps(result)


def test_missing_key_distinguished_from_null_and_unsupported(tmp_path):
    a = artifact(tmp_path, {"source_id": "source", "version": 1})
    assert exact_cell(tmp_path, [a], ref(a))["reason"] == "missing_key"
    b = artifact(tmp_path, {"rows": []})
    assert exact_cell(tmp_path, [b], ref(b))["status"] == "unsupported"
    assert exact_cell(tmp_path, [a], ref(a, kind="pdf"))["status"] == "unsupported"


def test_absent_row_requires_exact_frozen_coverage(tmp_path):
    a = artifact(tmp_path, {"source_id": "source", "version": 1, "rows": []})
    c = artifact(
        tmp_path,
        {"source_id": "coverage", "version": 2, "kind": "coverage", "rows": [{"zip": "94110"}]},
    )
    pin = {"source_id": "coverage", "version": 2, "sha256": c["sha256"]}
    citation = ref(a, row="94110", column="zip", expected_key="94110", coverage_sha256=c["sha256"])
    assert exact_cell(tmp_path, [a, c], citation, coverage_pin=pin) == {
        "status": "valid",
        "reason": "absent_row",
    }
    assert exact_cell(tmp_path, [a, c], citation)["status"] == "invalid"
    assert (
        exact_cell(tmp_path, [a, c], citation, coverage_pin=pin | {"version": 1})["status"]
        == "invalid"
    )
    present = artifact(tmp_path, {"source_id": "source", "version": 1, "rows": [{"zip": "94110"}]})
    citation.update(artifact_id=present["artifact_id"], sha256=present["sha256"])
    assert (
        exact_cell(tmp_path, [present, c], citation, coverage_pin=pin)["reason"]
        == "absent_row_present"
    )


@pytest.mark.parametrize("rows", [[], [{"zip": "94110"}], [{"zip": "94110", "count": 50}] * 2])
def test_missing_duplicate_rows_or_columns_are_invalid(tmp_path, rows):
    a = artifact(tmp_path, {"source_id": "source", "version": 1, "rows": rows})
    assert (
        exact_cell(tmp_path, [a], ref(a, row="94110", column="count", value="50"))["status"]
        == "invalid"
    )


def test_actual_output_byte_audit_and_initial_failure(evidence):
    for case, point, expected in [
        ("D01", "delivery", "valid"),
        ("D02", "initial", "invalid"),
        ("D02", "corrected", "valid"),
    ]:
        directory = evidence / case
        saved = json.loads((directory / f"checkpoint-{point}.json").read_bytes())
        assert (
            audit_artifacts(directory / "artifacts", saved["order"], saved["attempt"]["output"])[
                "status"
            ]
            == expected
        )


def test_extra_private_manifest_values_never_get_public_copy(evidence, tmp_path):
    import shutil

    directory = tmp_path / "case"
    shutil.copytree(evidence / "D01", directory)
    saved = json.loads((directory / "checkpoint-delivery.json").read_bytes())
    output = saved["attempt"]["output"]
    preview = output["preview"]
    raw = json.loads((directory / "artifacts" / preview["storage_key"]).read_bytes())
    raw["private_suppressed_count"] = 37
    output["preview"] = artifact(directory / "artifacts", raw)
    result = audit_artifacts(directory / "artifacts", saved["order"], output)
    assert result == {"status": "invalid", "reason": "preview_schema_mismatch", "public": []}
