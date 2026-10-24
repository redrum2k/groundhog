"""Independent byte checks; no runtime resolver, DTO validator or service calls.

The present-cell algorithm is extracted from Jeff's exact_cell in
tools/audit_primary_evidence.py, commit ef8c99afb9cf5f3b6928f505242f2d622fce2c3e
(also e774495192f903d0c1191590cf13cfc4a9439977), Git blob
51acbf86a90ff8f1cc3e7397db3fd7776ad2fc68. Explicit inputs replace private paths.
Extensions: unpublished attempt versions, CSV suppressed nulls, missing top-level
keys and coverage-pinned absent rows. Unsupported kinds are never scored as valid.
Usage reconciliation is unavailable: this lane has no observed provider usage.
"""

import csv
import hashlib
import io
import json

from evals.aggregate.schema import canonical


class AuditFailure(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise AuditFailure(code)


def read_bytes(root, artifact):
    path = (root / artifact["storage_key"]).resolve()
    require(path.is_relative_to(root.resolve()), "artifact_path_escape")
    require(path.is_file(), "artifact_missing")
    require(path.stat().st_size <= 2_000_000, "artifact_too_large")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == artifact["sha256"], "artifact_hash_mismatch")
    return raw


def data_bytes(root, artifact):
    raw = read_bytes(root, artifact)
    if artifact["media_type"] == "text/csv":
        return {"rows": list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))}
    require(artifact["media_type"] == "application/json", "unsupported_media")
    return json.loads(raw)


def exact_cell(root, artifacts, ref, *, deliveries=(), coverage_pin=None):
    """Return structural evidence only. Cell equality is not semantic entailment."""
    if ref.get("kind") != "dataset":
        return {"status": "unsupported", "reason": "reference_kind"}
    try:
        matches = [a for a in artifacts if a["artifact_id"] == ref["artifact_id"]]
        require(len(matches) == 1, "artifact_identity_ambiguous")
        artifact = matches[0]
        require(artifact["sha256"] == ref["sha256"], "reference_hash_mismatch")
        data = data_bytes(root, artifact)
        if artifact["media_type"] == "text/csv":
            require(ref["source_id"] == "delivery", "delivery_source_mismatch")
            versions = {
                d["version"]
                for d in deliveries
                if d["csv"]["artifact_id"] == artifact["artifact_id"]
            }
            require(ref["version"] in versions, "delivery_version_mismatch")
        elif "source_id" not in data or "version" not in data:
            return {"status": "unsupported", "reason": "json_without_source_identity"}
        else:
            require(data["source_id"] == ref["source_id"], "source_identity_mismatch")
            require(data["version"] == ref["version"], "source_version_mismatch")
        evidence = "present_cell"
        if ref.get("expected_key") is not None:
            require(coverage_pin is not None, "absence_requires_frozen_coverage")
            require(ref.get("coverage_sha256") == coverage_pin["sha256"], "coverage_hash_mismatch")
            covers = [a for a in artifacts if a["sha256"] == coverage_pin["sha256"]]
            require(len(covers) == 1, "coverage_artifact_missing")
            coverage = data_bytes(root, covers[0])
            require(
                coverage["source_id"] == coverage_pin["source_id"]
                and coverage["version"] == coverage_pin["version"]
                and coverage.get("kind") == "coverage",
                "coverage_identity_mismatch",
            )
            key = ref["expected_key"]
            require(ref["row"] == key and ref["column"] == "zip", "absence_target_mismatch")
            require(sum(r["zip"] == key for r in coverage["rows"]) == 1, "absence_outside_coverage")
            require(not any(r["zip"] == key for r in data["rows"]), "absent_row_present")
            value, evidence = None, "absent_row"
        elif ref["row"] == "$":
            evidence = "present_cell" if ref["column"] in data else "missing_key"
            value = data.get(ref["column"])
        else:
            rows = [r for r in data["rows"] if r["zip"] == ref["row"]]
            require(len(rows) == 1, "cell_row_not_unique")
            require(ref["column"] in rows[0], "cell_column_missing")
            value = rows[0][ref["column"]]
            if ref["column"] == "count" and rows[0].get("status") in ("suppressed", "unknown"):
                require(value is None or value == "", "unsafe_nonreleased_count")
                value = None
            if value is None:
                evidence = "null_cell"
        actual = (
            None if value is None else str(value).lower() if isinstance(value, bool) else str(value)
        )
        require(actual == ref["value"], "cell_value_mismatch")
        return {"status": "valid", "reason": evidence}
    except (AuditFailure, KeyError, ValueError, TypeError, OSError) as error:
        # Exception text from parsers can include private cell values. Only our codes escape.
        return {
            "status": "invalid",
            "reason": str(error)
            if isinstance(error, AuditFailure)
            else "malformed_or_missing_evidence",
        }


def safe_rows(rows):
    for row in rows:
        value = row.get("count")
        status = row.get("status")
        require(status in ("released", "suppressed", "unknown"), "invalid_row_status")
        if status != "released":
            require(value is None or value == "", "unsafe_nonreleased_count")
        else:
            require(
                not isinstance(value, bool)
                and str(value).isascii()
                and str(value).isdigit()
                and int(value) >= 50,
                "invalid_released_count",
            )


def audit_artifacts(root, order, delivery):
    """Reopen frozen sources and independently compare CSV, manifest and source rows."""
    try:
        terms = order["snapshot"]["quote"]["specification"]["terms"]
        sources = order["sources"]
        pins = [
            {
                "source_id": s["source_id"],
                "version": s["version"],
                "sha256": s["artifact"]["sha256"],
            }
            for s in sources
        ]
        require(pins == terms["sources"], "accepted_source_pins_mismatch")
        for source in sources:
            data = data_bytes(root, source["artifact"])
            require(
                data.get("source_id") == source["source_id"]
                and data.get("version") == source["version"],
                "source_version_mismatch",
            )
        if delivery is None:
            return {"status": "not_produced", "reason": "no_output_bytes", "public": []}
        csv_artifact, preview = delivery["csv"], delivery["preview"]
        raw = read_bytes(root, csv_artifact)
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        require(reader.fieldnames == terms["required_columns"], "csv_schema_mismatch")
        rows = list(reader)
        safe_rows(rows)
        normalized = [
            dict(r, count=int(r["count"]) if r["status"] == "released" else None) for r in rows
        ]
        keys = [r["zip"] for r in normalized]
        require(
            len(keys) == len(set(keys)) and set(keys) == set(terms["coverage"]["expected_keys"]),
            "coverage_mismatch",
        )
        manifest = data_bytes(root, preview)
        # Public copies must not smuggle extra private values beside valid rows.
        require(
            set(manifest)
            == {
                "schema_version",
                "columns",
                "csv_sha256",
                "specification_sha256",
                "sources",
                "coverage",
                "rows",
            }
            and manifest["schema_version"] == "aggregate-csv-v1",
            "preview_schema_mismatch",
        )
        require(manifest["csv_sha256"] == csv_artifact["sha256"], "preview_hash_mismatch")
        require(
            manifest["specification_sha256"] == hashlib.sha256(canonical(terms)).hexdigest(),
            "specification_hash_mismatch",
        )
        require(
            manifest["sources"] == pins and manifest["coverage"] == terms["coverage"]["pin"],
            "preview_pins_mismatch",
        )
        require(manifest["columns"] == terms["required_columns"], "preview_columns_mismatch")
        source = next(s for s in sources if s["source_id"].endswith(":" + terms["category"]))
        require(
            normalized == manifest["rows"] == data_bytes(root, source["artifact"])["rows"],
            "output_source_disagreement",
        )
        return {"status": "valid", "reason": "bytes_agree", "public": [csv_artifact, preview]}
    except (AuditFailure, KeyError, ValueError, TypeError, OSError, StopIteration) as error:
        return {
            "status": "invalid",
            "reason": str(error)
            if isinstance(error, AuditFailure)
            else "malformed_or_missing_evidence",
            "public": [],
        }
