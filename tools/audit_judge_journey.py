"""Independent byte/identity/settlement audit; never invokes runtime verdict code."""

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def verify_frozen_source(order, terms, expected, artifact):
    """Reconcile accepted derived bytes, not merely the learning bundle's values."""
    source = next(s for s in order["sources"] if s["source_id"].endswith(":" + terms["category"]))
    frozen = json.loads(artifact(source["artifact"]))
    assert frozen["source_id"] == source["source_id"] and frozen["version"] == source["version"]
    for field in (
        "category",
        "geography",
        "age_min",
        "age_max",
        "population",
        "count_unit",
        "groups_disjoint",
    ):
        assert frozen[field] == terms[field], ("accepted source scope differs", field)
    assert len(frozen["rows"]) == len(expected)
    assert {r["zip"]: (r["area"], r["count"], r["status"]) for r in frozen["rows"]} == expected


def verify_download(path, stored_bytes):
    downloaded = path.read_bytes()
    assert downloaded == stored_bytes, "downloaded artifact differs from immutable stored bytes"
    return downloaded


def audit(directory, *, output=None):
    directory = directory.resolve()
    report = load(directory / "report.json")
    assert report["completed"]
    state = directory.parent.parent
    database = (state / "orders.sqlite3").resolve()
    assert database == Path(report["database"]).resolve()
    artifacts = (state / "artifacts").resolve()
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    db.execute("BEGIN")

    def record(identifier, kind):
        row = db.execute("SELECT kind,body FROM im_records WHERE id=?", (identifier,)).fetchone()
        assert row and row[0] == kind
        result = json.loads(row[1])
        body = {k: v for k, v in result.items() if k != "id"}
        assert identifier == "institutional-" + digest({"kind": kind, "body": body})
        return result

    def catalog(kind, identifier):
        row = db.execute(
            "SELECT data FROM catalog_records WHERE kind=? AND id=?", (kind, identifier)
        ).fetchone()
        assert row, (kind, identifier)
        return json.loads(row[0])

    def artifact(metadata):
        path = (artifacts / metadata["storage_key"]).resolve()
        assert path.is_relative_to(artifacts)
        raw = path.read_bytes()
        assert sha(raw) == metadata["sha256"]
        return raw

    version = record(report["learning_version"], "source_version")
    qualification = record(version["qualification_id"], "source_qualification")
    assert qualification["passed"] and qualification["correct_both"] == qualification["cases"]
    assert version["implementation_sha256"] == qualification["implementation_sha256"]
    qtrace = json.loads(artifact(qualification["trace"]))
    assert all(
        arm["independently_verified"]
        and (not arm["ready"] or arm["composition"]["independently_verified"])
        for case in qtrace
        for arm in case["arms"].values()
    )
    proofs = {}
    for component_id in version["component_ids"]:
        component = record(component_id, "source_procedure")
        assert "rows" not in component and "final_answer" not in component
        resolution = record(component["resolution_id"], "source_resolution")
        proof = json.loads(artifact(resolution["evidence"]))
        assert proof["actor_id"] == resolution["actor_id"] == "simulated:DatumCo-local-source-owner"
        assert proof["origin"] == "explicitly_simulated_provider_resolution"
        witness = record(resolution["encounter_id"], "source_encounter")
        assert proof["source_pin"]["sha256"] == witness["case"]["source"]["artifact"]["sha256"]
        proofs[proof["source_family"]] = (proof, resolution["evidence"]["sha256"], component_id)
    assert len(proofs) >= 2 and len({v[1] for v in proofs.values()}) >= 2
    observations = []
    all_hashes = []
    for label, info in report["orders"].items():
        draft = catalog("request", info["run_id"])
        events = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT body FROM run_events WHERE run_id=? ORDER BY seq", (info["run_id"],)
            )
        ]
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
        if not info.get("order_id"):
            assert draft["status"] == "human_review" and draft["order_id"] is None
            saved = load(directory / (label + "-learning.json"))
            reviews = [r for r in saved["reviews"] if r["request_id"] == info["run_id"]]
            assert len(reviews) == 2 and all(r["reason"] == "authority_" + label for r in reviews)
            observations.append(
                {"case": label, "run_id": info["run_id"], "held_without_acceptance": True}
            )
            continue
        oid = info["order_id"]
        order = catalog("order", oid)
        delivered = load(directory / (label + "-delivered.json"))["order"]
        unfunded = load(directory / (label + "-unfunded.json"))["order"]
        assert (
            not unfunded["deliveries"]
            and not unfunded["ledger"]
            and unfunded["authorization"]["receipt"] is None
        )
        assert order["snapshot"] == delivered["snapshot"] == unfunded["snapshot"]
        assert draft["order_id"] == oid == order["snapshot"]["order_id"]
        assert order["snapshot"]["snapshot_id"] == info["snapshot_id"]
        assert order["snapshot"]["quote"]["request_id"] == info["run_id"]
        terms = order["snapshot"]["quote"]["specification"]["terms"]
        assert terms["policy_version"] == "aggregate-brokerage-v1"
        assert order["sources"] == order["snapshot"]["quote"]["sources"]
        pins = {(p["source_id"], p["version"], p["sha256"]) for p in terms["sources"]}
        assert pins == {
            (s["source_id"], s["version"], s["artifact"]["sha256"]) for s in order["sources"]
        }
        for source in order["sources"]:
            artifact(source["artifact"])
        bundle = record(info["source_bundle_id"], "source_bundle")
        expected, source_hashes = {}, []
        for part in bundle["partitions"]:
            raw = json.loads(artifact(part["source"]["artifact"]))
            head = json.loads(artifact(part["authority"]["artifact"]))
            proof, proof_sha, _ = proofs[raw["source_family"]]
            assert proof["scope"] == raw["scope"] == head["scope"]
            assert proof["authority_pin"]["sha256"] == part["authority"]["artifact"]["sha256"]
            assert head["status"] == "active" and not head["definitions"]
            assert proof_sha in {s["artifact"]["sha256"] for s in order["sources"]}
            source_hashes.append(part["source"]["artifact"]["sha256"])
            for row in raw["rows"]:
                assert row["zip"] not in expected
                expected[row["zip"]] = (
                    row["area"],
                    row["values"][proof["definition"]["column"]],
                    row["status"],
                )
        assert set(expected) == set(terms["coverage"]["expected_keys"])
        verify_frozen_source(order, terms, expected, artifact)
        assert len(order["deliveries"]) == 1 and order["free_corrections_used"] == 0
        delivery = order["deliveries"][0]
        raw_csv = artifact(delivery["csv"])
        assert raw_csv == (directory / (label + "-delivery.csv")).read_bytes()
        rows = list(csv.DictReader(raw_csv.decode().splitlines()))
        assert len(rows) == len(expected)
        assert {
            r["zip"]: (r["area"], int(r["count"]) if r["count"] else None, r["status"])
            for r in rows
        } == expected
        preview = json.loads(
            verify_download(directory / (label + "-delivery.json"), artifact(delivery["preview"]))
        )
        assert preview["csv_sha256"] == sha(raw_csv)
        assert {r["zip"]: (r["area"], r["count"], r["status"]) for r in preview["rows"]} == expected
        assert all(
            (count is None if status != "released" else type(count) is int and count >= 50)
            for _, count, status in expected.values()
        )
        learning = load(directory / (label + "-learning.json"))
        attempt = record(
            next(
                a["id"] for a in reversed(learning["attempts"]) if a["request_id"] == info["run_id"]
            ),
            "source_attempt",
        )
        assert attempt["source_hashes"] == source_hashes
        if label != "training":
            assert attempt["active_version"] == version["id"] and attempt["internal_reviews"] == 0
            assert attempt["baseline_reviews"] == 2
            for learned_id, baseline_id in zip(
                attempt["encounter_ids"], attempt["baseline_encounter_ids"], strict=True
            ):
                learned = record(learned_id, "source_encounter")
                baseline = record(baseline_id, "source_encounter")
                assert learned["case"] == baseline["case"]
                assert baseline["product_id"].endswith(":controlled-local-stateless-shadow")
                assert (
                    baseline["result"]["internal_reviews"] == 1
                    and baseline["result"]["normalized"] is None
                )
                assert learned["result"]["procedure_id"] in version["component_ids"]
            assert not set(source_hashes) & set(all_hashes)
        all_hashes.extend(source_hashes)
        assert len(order["ledger"]) == 1
        booking = order["ledger"][0]
        assert booking["amount"] == order["snapshot"]["quote"]["amount"]
        assert booking["receipt"]["mode"] == "mock" and booking["receipt"]["transaction_id"] is None
        assert booking["binding"]["snapshot_id"] == info["snapshot_id"]
        operations = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT data FROM payment_operations WHERE payment_id=?", (order["payment_id"],)
            )
        ]
        assert len(operations) == 2 and all(op["state"] == "confirmed" for op in operations)
        assert all(
            op["intent"]["order_id"] == oid
            and op["intent"]["snapshot_id"] == info["snapshot_id"]
            and op["intent"]["mode"] == "mock"
            and op["transaction_hash"] is None
            for op in operations
        )
        terminals = [
            op for op in operations if op["intent"]["action"] in ("capture", "void", "reclaim")
        ]
        assert len(terminals) == 1
        assert (
            db.execute(
                "SELECT count(*) FROM payment_effects WHERE payment_id=? AND kind='terminal'",
                (order["payment_id"],),
            ).fetchone()[0]
            == 1
        )
        if label == "later":
            held = load(directory / "later-held.json")["order"]
            assert not held["ledger"] and held["order_state"] == "human_review"
            assert all(a["result"] == "UNKNOWN" for a in held["semantic_findings"])
            assert booking["kind"] == "release" and terminals[0]["intent"]["action"] == "void"
            assert (
                len(order["decisions"]) == 1
                and order["decisions"][0]["action"] == "release_authorization"
            )
            assert booking["recorded_at"] >= order["decisions"][0]["recorded_at"]
            assert not any(e["type"] == "payment_captured" for e in events)
            attempts = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT data FROM catalog_records WHERE kind='dataset_assessment'"
                )
                if json.loads(r[0])["order_id"] == oid
            ]
            assert attempts and all(a["effective"]["result"] == "UNKNOWN" for a in attempts)
            spec_hash = sha(
                json.dumps(
                    order["snapshot"]["quote"]["specification"],
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            )
            assert all(a["accepted_specification_sha256"] == spec_hash for a in attempts)
            verdicts = [e["verdict"] for e in events if e["type"] == "verdict"]
            assert verdicts and all(
                v["decidedBy"]
                == (
                    "model"
                    if v["finding"]["validation"] == "VALIDATED"
                    and v["finding"]["effective"]["provenance"]["kind"] == "model"
                    else "unresolved"
                )
                and v["finding"]["attempt_id"] in {a["attempt_id"] for a in attempts}
                for v in verdicts
            )
            assert order == load(directory / "later-after-restart.json")["order"]
        else:
            assert booking["kind"] == "capture" and terminals[0]["intent"]["action"] == "capture"
            assert order["customer_acceptance"] == order["binding"]
            assert sum(e["type"] == "payment_captured" for e in events) == 1
            assert sum(e["type"] == "books_posted" for e in events) == 1
        if label == "scope-change":
            disposition = load(directory / "scope-change-disposition.json")["order"]
            assert disposition["cases"][-1]["status"] == "unsupported"
            assert not disposition["ledger"] and not disposition["children"]
            assert (
                terms["geography"] == "San Francisco" and terms["category"] == "gym_or_fitness_app"
            )
        observations.append(
            {
                "case": label,
                "run_id": info["run_id"],
                "order_id": oid,
                "snapshot_id": info["snapshot_id"],
                "rows_verified": len(rows),
                "source_hashes": source_hashes,
                "csv_sha256": sha(raw_csv),
                "baseline_reviews": attempt["baseline_reviews"],
                "reviews": attempt["internal_reviews"],
                "baseline_assessment_operations": attempt["baseline_operations"],
                "assessment_operations": attempt["machine_operations"],
                "terminal_booking": booking["kind"],
                "terminal_operation_id": terminals[0]["operation_id"],
            }
        )
    assert report["process_before"]["wrapper_pid"] != report["process_after"]["wrapper_pid"]
    trace = [json.loads(line) for line in (directory / "http-trace.jsonl").read_text().splitlines()]
    authorized = set()
    run_orders = {
        v["run_id"]: v["order_id"] for v in report["orders"].values() if v.get("order_id")
    }
    for entry in trace:
        path = entry["path"].removeprefix("/api/live")
        if entry["method"] == "POST" and entry["status"] < 300:
            if path.startswith("/orders/") and path.endswith("/acceptance"):
                authorized.add(path.split("/")[2])
            elif (
                path.startswith("/runs/")
                and path.endswith("/decisions")
                and entry["payload"]["action"] == "approve"
            ):
                authorized.add(run_orders[path.split("/")[2]])
        response = entry["response"]
        if isinstance(response, dict) and isinstance(response.get("order"), dict):
            observed = response["order"]
            if observed["ledger"]:
                assert observed["snapshot"]["order_id"] in authorized, (
                    "booking observed before explicit review/controller authorization"
                )
    assert any(t["status"] == 409 and t["key"].endswith(":stale-decision") for t in trace)
    assert report["retries_after_restart"] >= 10
    grouped = {}
    for entry in trace:
        if entry["method"] == "POST" and entry["status"] < 300:
            grouped.setdefault((entry["path"], entry["key"]), []).append(entry)
    repeated = [entries for entries in grouped.values() if len(entries) > 1]
    assert len(repeated) >= report["retries_after_restart"]
    assert all(
        all(
            e["payload"] == entries[0]["payload"] and e["response"] == entries[0]["response"]
            for e in entries
        )
        for entries in repeated
    )
    db.close()
    result = {
        "status": "VERIFIED",
        "git_commit": report["git_commit"],
        "read_only_database": True,
        "learning_version": version["id"],
        "training_human_interventions": len(proofs),
        "qualification_id": qualification["id"],
        "owner_evidence": [v[1] for v in proofs.values()],
        "observations": observations,
        "restart_and_retries": True,
        "repeated_commands_verified": len(repeated),
        "disclosure": (
            "Synthetic identities/data; mock settlement; deterministic or unresolved findings; "
            "no live LLM or human-time savings claim."
        ),
    }
    (output or directory / "independent-audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory, output=args.output), indent=2))
