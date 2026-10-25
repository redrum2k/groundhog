"""Bounded real-Claude qualification reusing the connected application journey.

Evaluator labels never enter application requests. No simulated model responses.
The existing cumulative budget and a hidden parent timeout supervise all calls.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.judge_journey import Journey, save

from aggregate_qualification import observe
from app.agents.budget import ModelBudget
from app.main import create_app
from primary_followup_eval import source_hash

AUTH = ROOT / ".local/llm-authorization.json"
ACCESS = ROOT / ".local/llm-access.json"
OUTPUT = ROOT / ".local/connected-model-qualification"
RECIPES = (
    {
        "id": "missing-zip",
        "text": "ZIP 94110 was omitted from our delivered CSV.",
        "expected": "FAIL",
        "basis": "The delivered row is present; independently reopen its actual CSV bytes.",
    },
    {
        "id": "scope-reasoning",
        "text": "Our agreement excludes yoga-only participants, so treating their absence as a delivery defect would change the deal.",
        "expected": "PASS",
        "basis": "Accepted explicit exclusion supports this statement; it alleges no output defect. Fresh compound paraphrase, not a canned grammar probe.",
    },
    {
        "id": "unproved-deduplication",
        "text": "Gym and app customers might appear in multiple ZIPs. Prove that the underlying people were deduplicated across ZIPs, not merely that each ZIP row occurs once.",
        "expected": "UNKNOWN",
        "basis": "Aggregate counts and a disjointness contract are not person-level identity evidence.",
    },
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def authorize():
    if ACCESS.exists():
        return load(ACCESS)
    auth = load(AUTH)
    path = Path(auth["ledger"])
    if not path.is_file():
        raise RuntimeError("Existing cumulative ledger required")
    budget = ModelBudget(path, cutoff=auth["cutoff"])
    before = budget.summary()
    if before["active"]:
        raise RuntimeError("Outstanding reservations must be reconciled before a new window")
    budget.register_authorized_window(
        auth["window"],
        starts_at=auth["start"],
        cutoff=auth["cutoff"],
        authorization_sha256=hashlib.sha256(AUTH.read_bytes()).hexdigest(),
    )
    # The unchanged reserve remains unavailable. This process's total cap permits
    # at most $5 beyond the cumulative conservative baseline, not another $45.
    maximum = min(
        before["maximum_usd"],
        round(
            before["conservative_committed_usd"]
            + before["final_evaluation_reserve_usd"]
            + auth["incremental_usd_cap"],
            6,
        ),
    )
    result = {"authorization": auth, "before": before, "maximum_usd": maximum}
    with ACCESS.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    return result


def configure():
    access = load(ACCESS)
    auth = access["authorization"]
    # Load only the API key from the existing private file; never echo its values
    # or copy the file into an artifact, worktree, child command line or PR.
    if not os.getenv("ANTHROPIC_API_KEY"):
        private = Path("C:/Users/sajee/order-to-cash/backend/.env")
        for line in private.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "ANTHROPIC_API_KEY":
                os.environ[key.strip()] = value.strip().strip("\"'")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Existing Anthropic credential unavailable")
    os.environ.update(
        {
            "CLAUDE_MODEL": auth["model"],
            "ENABLE_PAID_MODELS": "true",
            "ENABLE_DATASET_MODEL_ASSESSMENT": "true",
            "PAYMENT_ADAPTER": "mock",
            "ENABLE_TESTNET_BROADCAST": "false",
            "ENABLE_BROKER_DISPUTE_ASSESSMENT": "false",
            "APPLICATION_MODEL_BUDGET_PATH": auth["ledger"],
            "APPLICATION_MODEL_CUTOFF_AT": auth["cutoff"],
            "APPLICATION_MODEL_WINDOW_ID": auth["window"],
            "APPLICATION_MODEL_BUDGET_USD": str(access["maximum_usd"]),
            "APPLICATION_MODEL_CONCURRENCY": "1",
        }
    )
    budget = ModelBudget.configured()
    budget.check_window()
    return budget


class ConnectedJourney(Journey):
    def __init__(self, client, output):
        self.backend = client
        self.output = output
        self.id = uuid4().hex
        self.anchor = datetime.now(UTC)
        self.retries = []
        self.owner_walkthroughs = load(ROOT / "docs/examples/judge-owner-walkthroughs.json")
        self.report = {"orders": {}, "origin": "synthetic_training_and_authorized_real_claude"}

    def request(self, method, path, payload=None, *, key=None, bridge=True, expected=None):
        headers = {
            "X-Internal-Token": "qualification-worker",
            "X-Reviewer-Token": "qualification-reviewer",
            "X-Source-Owner-Token": "qualification-owner",
            "Idempotency-Key": key or self.id + ":" + uuid4().hex,
        }
        response = self.backend.request(method, path, json=payload, headers=headers)
        body = response.json()
        with (self.output / "http-trace.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "method": method,
                        "path": path,
                        "key": headers["Idempotency-Key"],
                        "payload": payload,
                        "status": response.status_code,
                        "response": body,
                    }
                )
                + "\n"
            )
        if expected is not None:
            assert response.status_code == expected, body
        else:
            response.raise_for_status()
        return body

    def assess(self, recipe, run, oid):
        original = self.order(oid)
        self.command(
            f"/orders/{oid}/complaints",
            {**self.bound(original), "text": recipe["text"]},
            recipe["id"] + ":plain-complaint",
            repeat=True,
        )
        current = self.wait(
            lambda: self.order(oid),
            lambda v: bool(v["order"]["semantic_findings"]),
            seconds=45,
        )
        order = current["order"]
        with sqlite3.connect(self.backend.app.state.orders.repository.path) as db:
            attempts = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT data FROM catalog_records WHERE kind='dataset_assessment'"
                )
                if json.loads(row[0])["order_id"] == oid
            ]
        assert len(attempts) == 1
        attempt = attempts[0]
        save(self.output / (recipe["id"] + "-attempt.json"), attempt)
        save(self.output / (recipe["id"] + "-assessed.json"), current)
        assert order["snapshot"] == original["order"]["snapshot"] and not order["ledger"]
        assert order["snapshot"]["quote"]["amount"] == "1.00"
        raw, effective = attempt["candidate"], attempt["effective"]
        result = {
            "case": recipe["id"],
            "order_id": oid,
            "raw": raw["result"] if raw else None,
            "effective": effective["result"],
            "status": attempt["status"],
            "raw_correct": bool(raw and raw["result"] == recipe["expected"]),
            "effective_correct": effective["result"] == recipe["expected"],
            "actual_model_response": bool(
                attempt["raw_response"] and raw and raw["provenance"]["kind"] == "model"
            ),
            "effective_model_provenance": effective["provenance"]["kind"] == "model",
            "raw_explanation": raw["explanation"] if raw else None,
        }
        if order["cases"][-1]["status"] == "unsupported":
            self.settle_review(recipe["id"], oid)
        else:
            # Preserve the unresolved/supported hold; never manufacture an answer
            # or approval to make this qualification look successful.
            save(self.output / (recipe["id"] + "-held.json"), current)
        save(self.output / (recipe["id"] + "-events.json"), self.page(run))
        return result


def application(root):
    return create_app(
        root / "orders.sqlite3",
        artifact_root=root / "artifacts",
        payment_mode="mock",
        internal_token="qualification-worker",
        reviewer_token="qualification-reviewer",
        source_owner_token="qualification-owner",
        source_learning=True,
        source_learning_model_qualification=True,
    )


def child(root):
    budget = configure()
    before_hash = source_hash()
    plan = {
        "lane": "LOCAL",
        "attempt": root.name,
        "recipes": RECIPES,
        "authorization_sha256": hashlib.sha256(AUTH.read_bytes()).hexdigest(),
        "source_sha256": before_hash,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "model": "claude-opus-5-5",
        "sdk_retries": 0,
        "concurrency": 1,
        "cutoff": load(AUTH)["cutoff"],
        "additional_spend_cap": 5,
        "criterion": "Raw model and effective findings must both be correct and model-provenanced; deterministic fallback is not success",
        "artifact_contract": "Actual HTTP commands/events, source/delivery bytes, raw model responses, persisted attempts, cumulative ledger reconciliation",
    }
    save(root / "frozen-plan.json", plan)
    save(
        root / "capsule.json",
        {
            "sha256": hashlib.sha256((root / "frozen-plan.json").read_bytes()).hexdigest(),
            "lane": "LOCAL",
        },
    )
    results = []
    try:
        with TestClient(application(root)) as client:
            gateway = client.app.state.orders.dataset_compiler
            assert gateway.__class__.__name__ == "ClaudeGateway"
            observe(gateway, root)
            journey = ConnectedJourney(client, root)
            run, oid = journey.intake("training", 301, ambiguous=True)
            journey.settle_review("training", oid)
            candidate = journey.command(
                "/source-learning/propose",
                {"target_id": journey.learning()["bundle_id"]},
                "propose",
            )["record_id"]
            journey.command("/source-learning/qualify", {"target_id": candidate}, "qualify")
            version = journey.command(
                "/source-learning/approve", {"target_id": candidate}, "approve"
            )["record_id"]
            journey.command("/source-learning/activate", {"target_id": version}, "activate")
            journey.report["learning_version"] = version
            for batch, recipe in enumerate(RECIPES, 302):
                run, oid = journey.intake(recipe["id"], batch)
                assert journey.report["orders"][recipe["id"]]["initial_internal_reviews"] == 0
                results.append(journey.assess(recipe, run, oid))
                save(root / "results.json", {"cases": results, "journey": journey.report})
            saved_orders = {
                label: journey.order(info["order_id"])["order"]
                for label, info in journey.report["orders"].items()
            }
            saved_learning = journey.learning()
        with TestClient(application(root)) as restarted:
            after = ConnectedJourney(restarted, root)
            assert after.learning()["active_version"] == saved_learning["active_version"]
            for label, info in journey.report["orders"].items():
                # Clocks continue; compare immutable accepted/decision/financial state.
                now = after.order(info["order_id"])["order"]
                for field in ("snapshot", "deliveries", "ledger", "decisions"):
                    assert now[field] == saved_orders[label][field]
            for retry in journey.retries:
                assert (
                    after.request("POST", retry["path"], retry["payload"], key=retry["key"])
                    == retry["response"]
                )
        assert source_hash() == before_hash
        save(
            root / "results.json",
            {
                "cases": results,
                "journey": journey.report,
                "restart_verified": True,
                "replayed_commands": len(journey.retries),
                "budget": budget.summary(),
                "source_sha256": before_hash,
            },
        )
    except BaseException as error:
        save(
            root / "failure.json",
            {
                "type": type(error).__name__,
                "message": str(error),
                "cases_completed": results,
                "budget": budget.summary(),
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--child", type=Path)
    parser.add_argument("--cohort", default="pilot")
    args = parser.parse_args()
    if args.authorize:
        print(json.dumps(authorize(), indent=2))
        return
    if args.child:
        child(args.child)
        return
    auth = load(AUTH)
    remaining = (datetime.fromisoformat(auth["cutoff"]) - datetime.now(UTC)).total_seconds()
    if remaining < 300:
        raise RuntimeError("Insufficient authorized time")
    if not args.cohort.replace("-", "").isalnum():
        raise ValueError("Use a simple new cohort identifier")
    root = OUTPUT / args.cohort
    root.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC).isoformat()
    with (root / "supervisor.log").open("x", encoding="utf-8") as log:
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", str(root)],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                timeout=min(900, remaining),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            result = {"exit_code": process.returncode}
        except subprocess.TimeoutExpired:
            result = {"terminated": True, "reason": "Independent authorized cutoff"}
    save(
        root / "supervisor.json",
        {"started": started, "ended": datetime.now(UTC).isoformat(), **result},
    )
    print(json.dumps({"evidence": str(root), **result}))


if __name__ == "__main__":
    main()
