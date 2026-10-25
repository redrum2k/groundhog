"""Independent saved-byte, model-usage and payment audit; no dispatch or verdict code."""

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from aggregate_qualification_audit import cost_micro

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_primary_evidence import exact_cell  # noqa: E402


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(root):
    plan, results = load(root / "frozen-plan.json"), load(root / "results.json")
    assert results["restart_verified"] and results["source_sha256"] == plan["source_sha256"]
    access = load(ROOT / ".local/llm-access.json")
    auth = access["authorization"]
    start = load(root / "supervisor.json")["started"]
    final_supervisor = root / "recovery-supervisor.json"
    if not final_supervisor.exists():
        final_supervisor = root / "supervisor.json"
    end = load(final_supervisor)["ended"]
    with sqlite3.connect(Path(auth["ledger"]).as_uri() + "?mode=ro", uri=True) as ledger:
        ledger.row_factory = sqlite3.Row
        calls = [
            dict(r)
            for r in ledger.execute(
                "SELECT * FROM calls WHERE window_id=? AND started_at>=? AND started_at<=? "
                "ORDER BY started_at",
                (auth["window"], start, end),
            )
        ]
        window_cost = ledger.execute(
            "SELECT sum(coalesce(actual_micro_usd,reserved_micro_usd)) "
            "FROM calls WHERE window_id=?",
            (auth["window"],),
        ).fetchone()[0]
        assert window_cost <= 5_000_000
    assert calls and all(r["status"] == "COMPLETE" for r in calls)
    assert sum(r["actual_micro_usd"] for r in calls) <= 5_000_000
    with sqlite3.connect((root / "orders.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")

        def record(identifier):
            kind, body = db.execute(
                "SELECT kind,body FROM im_records WHERE id=?", (identifier,)
            ).fetchone()
            value = json.loads(body)
            canonical = json.dumps(
                {"kind": kind, "body": {k: v for k, v in value.items() if k != "id"}},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            assert identifier == "institutional-" + hashlib.sha256(canonical.encode()).hexdigest()
            return value

        def artifact(meta):
            path = (root / "artifacts" / meta["storage_key"]).resolve()
            assert path.is_relative_to((root / "artifacts").resolve())
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
            return raw

        version = record(results["journey"]["learning_version"])
        qualification = record(version["qualification_id"])
        assert qualification["passed"]
        proofs = {}
        for component_id in version["component_ids"]:
            component = record(component_id)
            resolution = record(component["resolution_id"])
            proof = json.loads(artifact(resolution["evidence"]))
            assert proof["origin"] == "explicitly_simulated_provider_resolution"
            proofs[proof["source_family"]] = proof
        assert len(proofs) >= 2
        observed = []
        references = 0
        responses = [load(path)["raw_response"] for path in root.rglob("call-*.json")]
        for label, info in results["journey"]["orders"].items():
            order = json.loads(
                db.execute(
                    "SELECT data FROM catalog_records WHERE kind='order' AND id=?",
                    (info["order_id"],),
                ).fetchone()[0]
            )
            snapshot = order["snapshot"]
            terms = snapshot["quote"]["specification"]["terms"]
            assert snapshot["quote"]["request_id"] == info["run_id"]
            assert snapshot["snapshot_id"] == info["snapshot_id"]
            assert snapshot["quote"]["amount"] == {
                "amount_minor": 100,
                "currency": "USD",
                "decimals": 2,
            }
            assert order["sources"] == snapshot["quote"]["sources"]
            assert {
                (s["source_id"], s["version"], s["artifact"]["sha256"]) for s in order["sources"]
            } == {(s["source_id"], s["version"], s["sha256"]) for s in terms["sources"]}
            bundle = record(info["source_bundle_id"])
            expected = {}
            for part in bundle["partitions"]:
                source = json.loads(artifact(part["source"]["artifact"]))
                head = json.loads(artifact(part["authority"]["artifact"]))
                proof = proofs[source["source_family"]]
                assert source["scope"] == head["scope"] == proof["scope"]
                assert part["authority"]["artifact"]["sha256"] == proof["authority_pin"]["sha256"]
                for row in source["rows"]:
                    assert row["zip"] not in expected
                    expected[row["zip"]] = (
                        row["area"],
                        row["values"][proof["definition"]["column"]],
                        row["status"],
                    )
            # Validate the actual accepted derived source, not just bundle inputs.
            frozen = next(
                s for s in order["sources"] if s["source_id"].endswith(":" + terms["category"])
            )
            accepted = json.loads(artifact(frozen["artifact"]))
            assert accepted["category"] == terms["category"]
            for field in (
                "geography",
                "age_min",
                "age_max",
                "population",
                "count_unit",
                "groups_disjoint",
            ):
                assert accepted[field] == terms[field]
            assert {
                r["zip"]: (r["area"], r["count"], r["status"]) for r in accepted["rows"]
            } == expected
            delivery = order["deliveries"][0]
            raw_csv, raw_json = artifact(delivery["csv"]), artifact(delivery["preview"])
            assert raw_csv == (root / (label + "-delivery.csv")).read_bytes()
            assert raw_json == (root / (label + "-delivery.json")).read_bytes()
            rows = list(csv.DictReader(raw_csv.decode().splitlines()))
            assert len(rows) == len(expected) == 27
            assert {
                r["zip"]: (r["area"], int(r["count"]) if r["count"] else None, r["status"])
                for r in rows
            } == expected
            preview = json.loads(raw_json)
            assert preview["csv_sha256"] == hashlib.sha256(raw_csv).hexdigest()
            assert {
                r["zip"]: (r["area"], r["count"], r["status"]) for r in preview["rows"]
            } == expected
            learning = load(root / (label + "-learning.json"))
            attempt = next(
                a for a in reversed(learning["attempts"]) if a["request_id"] == info["run_id"]
            )
            if label != "training":
                assert attempt["active_version"] == version["id"]
                assert attempt["internal_reviews"] == 0 and attempt["baseline_reviews"] == 2
                assessment = load(root / (label + "-attempt.json"))
                assert assessment["order_id"] == info["order_id"]
                specification = json.dumps(
                    snapshot["quote"]["specification"],
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
                assert (
                    assessment["accepted_specification_sha256"]
                    == hashlib.sha256(specification).hexdigest()
                )
                expected = next(r["expected"] for r in plan["recipes"] if r["id"] == label)
                outcome = next(r for r in results["cases"] if r["case"] == label)
                assert outcome["raw"] == assessment["candidate"]["result"]
                assert outcome["effective"] == assessment["effective"]["result"]
                assert outcome["raw_correct"] == (outcome["raw"] == expected)
                assert outcome["effective_correct"] == (outcome["effective"] == expected)
                assert outcome["effective_model_provenance"] == (
                    assessment["effective"]["provenance"]["kind"] == "model"
                )
                provider_text = "".join(
                    block["text"]
                    for block in assessment["raw_response"]["content"]
                    if block["type"] == "text"
                )
                assert json.loads(provider_text)["result"] == outcome["raw"]
                assert assessment["candidate"]["provenance"]["kind"] == "model"
                all_attempts = root / (label + "-attempts.json")
                attempts = load(all_attempts) if all_attempts.exists() else [assessment]
                assert not load(root / (label + "-assessed.json"))["order"]["ledger"]
                for saved in attempts:
                    assert saved["order_id"] == info["order_id"]
                    assert (
                        saved["accepted_specification_sha256"]
                        == hashlib.sha256(specification).hexdigest()
                    )
                    responses.append(saved["raw_response"])
                    for key in ("candidate", "effective"):
                        for ref in (*saved[key]["citations"], *saved[key]["conflicting_evidence"]):
                            exact_cell(root, order, ref)
                            references += 1
                    if saved.get("review_response"):
                        responses.append(saved["review_response"])
                        review = saved["review"]
                        if saved["status"] == "VALIDATED":
                            assert review["result"] == saved["candidate"]["result"]
                            assert " ".join(
                                " ".join(c["text"] for c in review["clauses"]).split()
                            ) == " ".join(saved["review_request"]["complaint"].split())
                            for clause in review["clauses"]:
                                assert clause["result"] == review["result"] and clause["citations"]
                                for ref in clause["citations"]:
                                    exact_cell(root, order, ref)
                                    references += 1
            operations = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT data FROM payment_operations WHERE payment_id=?", (order["payment_id"],)
                )
            ]
            assert all(
                op["intent"]["mode"] == "mock" and not op["transaction_hash"] for op in operations
            )
            assert all(
                op["intent"]["order_id"] == info["order_id"]
                and op["intent"]["snapshot_id"] == info["snapshot_id"]
                for op in operations
            )
            terminals = [op for op in operations if op["intent"]["action"] != "fund"]
            if label in ("training", "missing-zip", "excluded-population"):
                assert len(terminals) == len(order["ledger"]) == 1
                assert order["ledger"][0]["kind"] == "capture"
            elif plan["attempt"] == "semantic-v1":
                assert len(terminals) == len(order["ledger"]) == 1
                assert order["ledger"][0]["kind"] == "release"
                assert len(order["decisions"]) == 1
                assert order["decisions"][0]["action"] == "release_authorization"
            else:
                assert not terminals and not order["ledger"]
            observed.append(
                {
                    "case": label,
                    "rows": len(rows),
                    "reviews": attempt["internal_reviews"],
                    "bookings": len(order["ledger"]),
                }
            )
    unmatched = {r["id"]: r for r in calls}
    ids = set()
    for response in responses:
        assert response and response["model"] == "claude-opus-5-5" and response["id"] not in ids
        ids.add(response["id"])
        matches = [
            r for r in unmatched.values() if json.loads(r["usage_json"]) == response["usage"]
        ]
        assert matches
        row = unmatched.pop(matches[0]["id"])
        assert cost_micro(response["usage"]) == row["actual_micro_usd"]
    assert not unmatched
    result = {
        "evidence_verified": True,
        "raw_cases_correct": sum(c["raw_correct"] for c in results["cases"]),
        "effective_cases_correct": sum(
            c["effective_correct"] and c["effective_model_provenance"] for c in results["cases"]
        ),
        "cases": results["cases"],
        "observations": observed,
        "model_calls": len(calls),
        "total_authorized_window_cost_usd": window_cost / 1e6,
        "cost_usd": sum(r["actual_micro_usd"] for r in calls) / 1e6,
        "citations_independently_checked": references,
        "combined_qualification_passed": all(
            c["raw_correct"] and c["effective_correct"] and c["effective_model_provenance"]
            for c in results["cases"]
        ),
        "restart_verified": True,
        "disclosure": (
            "Real Claude, simulated source-owner testimony/data, mock payments; "
            "author-defined cases, not independent human evaluation."
        ),
    }
    (root / "independent-model-audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(audit(parser.parse_args().directory.resolve()), indent=2))
