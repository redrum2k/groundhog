"""Additional read-only source approval/pin audit of original executed bytes."""

from datetime import datetime

from evals.roi.plan import save
from evals.roi.scoring import artifact, load


def check_lineage(case, result, records, root):
    version_id = result.get("reused_procedure")
    if not version_id:
        return 0
    maps = {kind: {r["id"]: r for r in rows} for kind, rows in records.items()}
    version = maps["source_version"][version_id]
    qualification = maps["source_qualification"][version["qualification_id"]]
    assert version["approved_by"] == "controller:roi"
    assert qualification["passed"] and not qualification["violations"]
    assert qualification["candidate_id"] == version["candidate_id"]
    assert qualification["correct_both"] == qualification["cases"] == 6
    artifact(root, qualification["capsule"])
    artifact(root, qualification["trace"])
    attempts = [
        a
        for a in records["source_attempt"]
        if a["request_id"] == result["request_id"] and a["active_version"] == version_id
    ]
    assert attempts
    encounters = [
        maps["source_encounter"][identifier]["case"] for identifier in attempts[-1]["encounter_ids"]
    ]
    assert len(encounters) == len(version["component_ids"]) == len(case["source"]["partitions"])
    checked = 0
    for identifier in version["component_ids"]:
        procedure = maps["source_procedure"][identifier]
        binding = procedure["binding"]
        part = next(
            p
            for p in case["source"]["partitions"]
            if p["export"]["source_family"] == binding["source_family"]
        )
        raw, head = part["export"], part["authority"]
        encounter = next(e for e in encounters if e["source"]["source_id"] == raw["source_id"])
        current_authority = encounter["authority"]
        assert binding["authority"] == {
            "source_id": current_authority["source_id"],
            "version": current_authority["version"],
            "sha256": current_authority["artifact"]["sha256"],
        }
        assert load_bytes(root, current_authority["artifact"]) == head
        assert load_bytes(root, encounter["source"]["artifact"]) == raw
        assert head["status"] == "active" and datetime.fromisoformat(
            head["valid_until"]
        ) > datetime.fromisoformat("2026-10-24T12:00:00+00:00")
        assert binding["scope"] == raw["scope"] == head["scope"]
        assert binding["schema_version"] == raw["schema_version"] == head["source_version"]
        assert binding["schema_hash"] == head["schema_hash"]
        assert binding["publisher"] == raw["publisher"] == head["publisher"]
        resolution = maps["source_resolution"][procedure["resolution_id"]]
        proof = load_bytes(root, resolution["evidence"])
        assert proof["origin"] == "explicitly_simulated_provider_resolution"
        assert proof["authority_pin"] == binding["authority"]
        assert proof["definition"]["column"] == procedure["column"]
        assert proof["source_pin"]["sha256"] != encounter["source"]["artifact"]["sha256"]
        checked += 1
    return checked


def load_bytes(root, metadata):
    import json

    return json.loads(artifact(root, metadata))


def audit(directory):
    report, plan = load(directory / "results.json"), load(directory / "inputs.json")
    inputs = {c["case_id"]: c for c in plan["setup"] + plan["cases"]}
    checked, reused, invalid_held = 0, 0, 0
    for result in report["cases"]:
        if result["arm"] != "approved_learning":
            continue
        case = inputs[result["case_id"]]
        root = directory / "arms" / result["arm"] / result["stream_id"]
        records = load(root / "cases" / case["case_id"] / "learning-records.json")
        count = check_lineage(case, result, records, root / "artifacts")
        checked += count
        reused += int(bool(count))
        if case["action"] == "source_hold":
            assert (
                not count
                and not result["orders"]
                and result["observed_disposition"] == "held_before_acceptance"
            )
            invalid_held += 1
    summary = dict(
        status="VERIFIED",
        reused_cases=reused,
        fresh_component_bindings_checked=checked,
        invalid_source_cases_held=invalid_held,
        runtime_modified=False,
        new_model_calls=0,
        scope=(
            "Exact current authority pins, schema/scope/publisher, "
            "persisted approval/qualification and fresh input hashes"
        ),
    )
    save(directory / "lineage-audit.json", summary)
    return summary
