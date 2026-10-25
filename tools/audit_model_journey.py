"""Read-only live-model/citation audit. No model SDK, runtime verdict or training inputs."""

import argparse
import ast
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def frozen_module(commit, path):
    """Read the tested source, not a possibly changed prompt or executable SDK."""
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    source = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout
    return ast.parse(source)


def dispatched_request_hash(packet, model, commit, *, review=False):
    """Reconstruct the reserved envelope from frozen literals and saved input.

    No gateway/client is instantiated and no production function is executed.
    A schema or prompt mismatch fails the ledger hash check, never falls back to usage.
    """
    from app.contracts.catalog import Assessment
    from app.contracts.semantic import DatasetClaimReview

    gateway = frozen_module(commit, "backend/app/agents/gateway.py")
    module = frozen_module(commit, "backend/app/investigation/dataset.py") if review else gateway
    name = "review_dataset_claim" if review else "assess_obligation"
    functions = [n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name]
    instruction = next(
        ast.literal_eval(n.args[1])
        for function in functions
        for n in ast.walk(function)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "parse"
        and len(n.args) == 3
    )
    prefix = next(
        ast.literal_eval(n.value.left)
        for n in ast.walk(gateway)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "system" for t in n.targets)
    )
    constants = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in gateway.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {"MODEL_OUTPUT_TOKENS", "MODEL_TIMEOUT_SECONDS"}
    }
    payload = (
        packet
        if review
        else {
            "requirement": packet["obligation"],
            "claim": packet["claim"],
            "evidence": packet["passages"],
        }
    )
    envelope = {
        "model": model,
        "max_tokens": constants["MODEL_OUTPUT_TOKENS"],
        "timeout": constants["MODEL_TIMEOUT_SECONDS"],
        "output_format": (DatasetClaimReview if review else Assessment).model_json_schema(),
        "system": prefix + instruction,
        "messages": [{"role": "user", "content": json.dumps(payload, sort_keys=True)}],
    }
    return hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()


def match_response(raw, calls, *, request_hash, model, purpose):
    assert raw and raw["model"] == model and raw["stop_reason"] == "end_turn"
    assert raw["id"].startswith("msg_") and raw["usage"]
    matches = [
        c
        for c in calls
        if c["request_sha256"] == request_hash and c["model"] == model and c["purpose"] == purpose
    ]
    assert len(matches) == 1, "Response must bind to exactly one dispatched request"
    call = matches[0]
    assert json.loads(call["usage_json"]) == raw["usage"], "Bound request usage differs"
    calls.remove(call)
    return {"call_id": call["id"], "request_sha256": request_hash, "response_id": raw["id"]}


def audit(directory, capsule_path, access_path, *, output=None):
    report, capsule = load(directory / "report.json"), load(capsule_path)
    assert report["completed"] and report["git_commit"] == capsule["git_commit"]
    assert not report["source_tree_dirty"] and report["model_mode"] == "real_provider"
    state = directory.parent.parent
    db = sqlite3.connect((state / "orders.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("BEGIN")
    access = load(access_path)
    ledger = sqlite3.connect(
        Path(access["authorization"]["ledger"]).resolve().as_uri() + "?mode=ro", uri=True
    )
    ledger.row_factory = sqlite3.Row
    start, end = (datetime.fromisoformat(report[k]) for k in ("started_at", "completed_at"))
    calls = [
        dict(r)
        for r in ledger.execute("SELECT * FROM calls")
        if start <= datetime.fromisoformat(r["started_at"]) <= end
    ]
    assert len(calls) == report["paid_calls"]
    assert all(c["status"] == "COMPLETE" and c["actual_micro_usd"] is not None for c in calls)
    assert all(c["model"] == capsule["model"] and c["usage_json"] for c in calls)
    unmatched = list(calls)

    def artifact(metadata):
        root = (state / "artifacts").resolve()
        path = (root / metadata["storage_key"]).resolve()
        assert path.is_relative_to(root)
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
        return raw

    def exact_reference(order, ref):
        meta = next(a for a in order["artifacts"] if a["artifact_id"] == ref["artifact_id"])
        assert meta["sha256"] == ref["sha256"] and ref["expected_key"] is None
        raw = artifact(meta)
        if meta["media_type"] == "text/csv":
            delivery = next(
                d for d in order["deliveries"] if d["csv"]["artifact_id"] == ref["artifact_id"]
            )
            assert ref["source_id"] == "delivery" and ref["version"] == delivery["version"]
            data = {"rows": list(csv.DictReader(raw.decode().splitlines()))}
        else:
            data = json.loads(raw)
            assert data["source_id"] == ref["source_id"] and data["version"] == ref["version"]
        if ref["row"] == "$":
            value = data[ref["column"]]
        else:
            rows = [r for r in data["rows"] if r["zip"] == ref["row"]]
            assert len(rows) == 1
            value = rows[0][ref["column"]]
            if (
                meta["media_type"] == "text/csv"
                and ref["column"] == "count"
                and rows[0]["status"] == "suppressed"
            ):
                assert value == ""
                value = None
        normalized = (
            None if value is None else str(value).lower() if isinstance(value, bool) else str(value)
        )
        assert normalized == ref["value"]

    response_bindings = []

    def provider_response(raw, packet, *, review=False):
        assert raw["id"] not in {b["response_id"] for b in response_bindings}
        response_bindings.append(
            match_response(
                raw,
                unmatched,
                request_hash=dispatched_request_hash(
                    packet, capsule["model"], report["git_commit"], review=review
                ),
                model=capsule["model"],
                purpose="primary-dataset-claim-review" if review else "primary-dataset-dispute",
            )
        )

    results = []
    for label, expected, text in (
        ("later", "UNKNOWN", capsule["objection"]),
        ("after-restart", "FAIL", capsule["after_restart_objection"]),
    ):
        info = report["orders"][label]
        order = json.loads(
            db.execute(
                "SELECT data FROM catalog_records WHERE kind='order' AND id=?", (info["order_id"],)
            ).fetchone()[0]
        )
        assert order["cases"][-1]["complaint"]["text"] == text
        attempts = [
            json.loads(r[0])
            for r in db.execute("SELECT data FROM catalog_records WHERE kind='dataset_assessment'")
            if json.loads(r[0])["order_id"] == info["order_id"]
        ]
        refs_checked, blind = 0, 0
        assert attempts
        for attempt in attempts:
            assert attempt["candidate"]["result"] == attempt["effective"]["result"] == expected
            assert attempt["effective"]["provenance"]["kind"] == "model"
            assert text in attempt["request"]["claim"]
            provider_response(attempt["raw_response"], attempt["request"])
            refs = attempt["candidate"]["citations"] + attempt["effective"]["citations"]
            if attempt.get("review_response"):
                blind += 1
                provider_response(
                    attempt["review_response"], attempt["review_request"], review=True
                )
                packet = attempt["review_request"]
                assert set(packet) == {"complaint", "frozen_evidence_packet"}
                assert packet["complaint"] == text
                assert attempt["candidate"]["explanation"] not in json.dumps(packet)
                assert attempt["review"]["result"] == expected
                refs += [r for clause in attempt["review"]["clauses"] for r in clause["citations"]]
            for ref in refs:
                exact_reference(order, ref)
                refs_checked += 1
        rows = list(csv.DictReader(artifact(order["deliveries"][-1]["csv"]).decode().splitlines()))
        if label == "after-restart":
            assert (
                next(int(r["count"]) for r in rows if r["zip"] == capsule.get("count_zip", "94103"))
                > 0
            )
            assert blind == 1 and order["ledger"][0]["kind"] == "capture"
            before_money = load(directory / "after-restart-disposition.json")["order"]
            assert not before_money["ledger"] and before_money["customer_acceptance"] is None
        else:
            assert set(rows[0]) == {"zip", "area", "count", "status"}
            assert order["ledger"][0]["kind"] == "release"
            assert order["decisions"][-1]["action"] == "release_authorization"
        results.append(
            {
                "case": label,
                "expected": expected,
                "raw": expected,
                "effective": expected,
                "attempts": len(attempts),
                "blind_reviews": blind,
                "references_verified": refs_checked,
            }
        )
    # Other completed calls are intake, not additional semantic accuracy samples.
    assert all(c["purpose"] != "primary-dataset-dispute" for c in unmatched)
    result = {
        "status": "VERIFIED",
        "tested_commit": report["git_commit"],
        "capsule_sha256": hashlib.sha256(capsule_path.read_bytes()).hexdigest(),
        "actual_completed_provider_requests": len(calls),
        "raw_dispute_responses_verified": len(calls) - len(unmatched),
        "response_bindings": response_bindings,
        "other_completed_calls": [
            {"purpose": c["purpose"], "request_sha256": c["request_sha256"], "usage_recorded": True}
            for c in unmatched
        ],
        "estimated_usd": sum(c["actual_micro_usd"] for c in calls) / 1e6,
        "cases": results,
        "limitations": [
            "Engineering scenarios, not an independent human holdout or accuracy estimate.",
            "Raw intake responses are not retained by this application driver; "
            "completed budget usage and proposals are retained.",
            "No live payment, production activation, or human-time savings claim.",
        ],
    }
    db.close()
    ledger.close()
    destination = output or directory / "independent-model-audit.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, help="Keep a re-audit separate from original evidence"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            audit(args.directory.resolve(), args.capsule, args.access, output=args.output), indent=2
        )
    )
