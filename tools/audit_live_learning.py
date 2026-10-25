"""Independent read-only audit of the actual HTTP demonstration's persisted bytes."""

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/live-learning"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    directory = args.session.resolve()
    assert directory.is_relative_to(LOCAL.resolve())
    session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    db = sqlite3.connect(f"file:{(LOCAL / 'orders.sqlite3').as_posix()}?mode=ro", uri=True)

    def record(identifier, expected_kind):
        row = db.execute("SELECT kind,body FROM im_records WHERE id=?", (identifier,)).fetchone()
        assert row and row[0] == expected_kind
        data = json.loads(row[1])
        assert (
            "institutional-"
            + digest({"kind": row[0], "body": {k: v for k, v in data.items() if k != "id"}})
            == identifier
        )
        return data

    def artifact(metadata):
        root = (LOCAL / "artifacts").resolve()
        path = (root / metadata["storage_key"]).resolve()
        assert path.is_relative_to(root)
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
        return json.loads(raw)

    version = record(session["active_version"], "source_version")
    qualification = record(version["qualification_id"], "source_qualification")
    assert qualification["passed"] and qualification["correct_both"] == qualification["cases"]
    assert qualification["implementation_sha256"] == version["implementation_sha256"]
    capsule = artifact(qualification["capsule"])
    assert capsule["implementation_sha256"] == version["implementation_sha256"]
    traces = artifact(qualification["trace"])
    assert all(arm["independently_verified"] for case in traces for arm in case["arms"].values())
    evidence, components = [], []
    for identifier in version["component_ids"]:
        component = record(identifier, "source_procedure")
        assert "rows" not in component and "final_answer" not in component
        resolution = record(component["resolution_id"], "source_resolution")
        proof = artifact(resolution["evidence"])
        assert proof["origin"] == "explicitly_simulated_provider_resolution"
        assert proof["actor_id"] == resolution["actor_id"] == "simulated:DatumCo-local-source-owner"
        evidence.append(resolution["evidence"]["sha256"])
        components.append(
            {
                "procedure_id": identifier,
                "resolution_id": resolution["id"],
                "evidence_sha256": resolution["evidence"]["sha256"],
                "family": proof["source_family"],
            }
        )
    assert len(set(evidence)) >= 2 and len({c["family"] for c in components}) >= 2
    observations = []
    for label in ("later", "after-restart"):
        result = json.loads((directory / (label + "-result.json")).read_text(encoding="utf-8"))
        attempt = record(result["same_byte_comparison"]["id"], "source_attempt")
        assert attempt["active_version"] == version["id"]
        expected = {}
        actual_hashes = []
        for identifier, baseline_id in zip(
            attempt["encounter_ids"], attempt["baseline_encounter_ids"], strict=True
        ):
            candidate = record(identifier, "source_encounter")
            baseline = record(baseline_id, "source_encounter")
            assert baseline["product_id"].endswith(":controlled-local-stateless-shadow")
            assert candidate["case"] == baseline["case"]
            assert candidate["result"]["binding"] == baseline["result"]["binding"]
            case = candidate["case"]
            raw, head = (
                artifact(case["source"]["artifact"]),
                artifact(case["authority"]["artifact"]),
            )
            assert head["status"] == "active" and not head["definitions"]
            assert baseline["result"]["reason"] == "ambiguous_source_definition"
            assert (
                baseline["result"]["internal_reviews"] == 1
                and baseline["result"]["normalized"] is None
            )
            assert candidate["result"]["procedure_id"] in version["component_ids"]
            procedure = record(candidate["result"]["procedure_id"], "source_procedure")
            resolution = record(procedure["resolution_id"], "source_resolution")
            proof = artifact(resolution["evidence"])
            assert proof["authority_pin"]["sha256"] == case["authority"]["artifact"]["sha256"]
            assert proof["source_pin"]["sha256"] != case["source"]["artifact"]["sha256"]
            assert proof["scope"] == raw["scope"] and proof["source_family"] == raw["source_family"]
            column = proof["definition"]["column"]
            partition = {row["zip"]: (row["values"][column], row["status"]) for row in raw["rows"]}
            assert not set(partition) & set(expected)
            assert {
                r["zip"]: (r["count"], r["status"])
                for r in candidate["result"]["normalized"]["rows"]
            } == partition
            assert candidate["result"]["internal_reviews"] == 0
            expected.update(partition)
            actual_hashes.append(case["source"]["artifact"]["sha256"])
        assert actual_hashes == attempt["source_hashes"]
        data = (directory / (label + "-delivery.csv")).read_bytes()
        assert hashlib.sha256(data).hexdigest() == result["csv_sha256"]
        rows = list(csv.DictReader(data.decode().splitlines()))
        assert len(rows) == len(expected) == 27
        assert {
            r["zip"]: (int(r["count"]) if r["count"] else None, r["status"]) for r in rows
        } == expected
        observations.append(
            {
                "phase": label,
                "request_id": result["request_id"],
                "both_arms_verified": True,
                "baseline_reviews": attempt["baseline_reviews"],
                "candidate_reviews": attempt["internal_reviews"],
                "baseline_assessment_operations": attempt["baseline_operations"],
                "candidate_assessment_operations": attempt["machine_operations"],
                "verified_rows": len(rows),
                "new_source_hashes": actual_hashes,
                "csv_sha256": result["csv_sha256"],
            }
        )
    assert session["initial_process"]["wrapper_pid"] != session["restarted_process"]["wrapper_pid"]
    report = {
        "status": "VERIFIED",
        "read_only_database_audit": True,
        "active_version": version["id"],
        "approved_by": version["approved_by"],
        "qualification_id": qualification["id"],
        "capsule_sha256": qualification["capsule_sha256"],
        "components": components,
        "observations": observations,
        "restart_persistence": True,
        "interpretation": (
            "Synthetic source-owner/controller identities and engineering cases; "
            "no measured human time or unrestricted production claim."
        ),
    }
    (directory / "independent-audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    db.close()


if __name__ == "__main__":
    main()
