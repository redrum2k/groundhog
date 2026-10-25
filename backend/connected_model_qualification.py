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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from aggregate_qualification import observe
from app.agents.budget import ModelBudget
from app.main import create_app
from primary_followup_eval import source_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.judge_journey import Journey, save  # noqa: E402

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
        "text": (
            "Our agreement excludes yoga-only participants, so treating their absence "
            "as a delivery defect would change the deal."
        ),
        "expected": "PASS",
        "basis": (
            "Accepted explicit exclusion supports this statement; it alleges no output "
            "defect. Fresh compound paraphrase, not a canned grammar probe."
        ),
    },
    {
        "id": "unproved-deduplication",
        "text": (
            "Gym and app customers might appear in multiple ZIPs. Prove that the underlying "
            "people were deduplicated across ZIPs, not merely that each ZIP row occurs once."
        ),
        "expected": "UNKNOWN",
        "basis": (
            "Aggregate counts and a disjointness contract are not person-level identity evidence."
        ),
    },
)

SEMANTIC_CASES = (
    {
        "id": "excluded-population",
        "text": (
            "Leaving out people whose only activity is yoga violates our agreement; "
            "those people belonged in the deliverable."
        ),
        "expected": "FAIL",
        "basis": "Accepted exclusion contradicts both clauses; real model interpretation required.",
    },
    {
        "id": "scope-confirmation",
        "text": (
            "The purchased population was gym members or fitness-app users, not people who "
            "only attend yoga. Their exclusion is consistent with what we accepted."
        ),
        "expected": "PASS",
        "basis": (
            "Both clauses describe the frozen agreed category without alleging an output fault."
        ),
    },
    {
        "id": "identity-evidence",
        "text": (
            "A person with homes in two ZIPs could be in both totals. Show the underlying "
            "identity matching evidence that rules this out, beyond the contract's assumption."
        ),
        "expected": "UNKNOWN",
        "basis": "Person-level matching evidence is absent; do not infer it from aggregate rows.",
    },
)

FINAL_CASES = (
    {
        "id": "misread-scope",
        "text": (
            "You sold us an audience that includes yoga-only members. "
            "Removing them fails the agreed specification."
        ),
        "expected": "FAIL",
        "basis": "Both assertions conflict with the accepted exclusion; no extra-scope consent.",
    },
    {
        "id": "scope-boundary",
        "text": (
            "A customer enrolled only in a yoga studio is outside the gym-or-app audience "
            "we bought; excluding that customer does not break our scope."
        ),
        "expected": "PASS",
        "basis": "Accepted source/category supports the exclusion and its scope consequence.",
    },
    {
        "id": "unverified-identity",
        "text": (
            "I believe some residents were counted in more than one ZIP. The terms assume "
            "disjoint groups, but I need identity-level evidence to settle that concern."
        ),
        "expected": "UNKNOWN",
        "basis": "No person-level linkage evidence exists in the accepted aggregate artifacts.",
    },
)

CONTEXT_CASES = (
    {
        "id": "contract-promise",
        "text": (
            "Under the deal we accepted, people with only a yoga membership were part of "
            "what I purchased; leaving that group out breaches that deal."
        ),
        "expected": "FAIL",
        "basis": "The agreed exclusion contradicts contractual inclusion and the breach assertion.",
    },
    {
        "id": "agreed-limit",
        "text": (
            "The package I bought was the union of gym members and fitness-app users. "
            "Someone whose sole membership is a yoga studio was not part of that agreed audience."
        ),
        "expected": "PASS",
        "basis": "Both contractual assertions are supported by accepted terms and category evidence.",
    },
    {
        "id": "source-dedup",
        "text": (
            "The signed specification says the ZIP groups are disjoint. However, I am alleging "
            "that the actual source counts include the same person in two ZIPs, and I need "
            "record-level matching evidence."
        ),
        "expected": "UNKNOWN",
        "basis": "The empirical allegation remains unproved despite the contract's disjointness rule.",
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
        original = load(self.output / (recipe["id"] + "-delivered.json"))
        saved = self.output / (recipe["id"] + "-assessed.json")
        if saved.exists():
            current = load(saved)  # Technical recovery: no repeated model dispatch.
        else:
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
        if saved.exists():
            attempt = load(self.output / (recipe["id"] + "-attempt.json"))
        else:
            assert len(attempts) == 1
            attempt = attempts[0]
        if not saved.exists():
            save(self.output / (recipe["id"] + "-attempt.json"), attempt)
            save(saved, current)
        assert order["snapshot"] == original["order"]["snapshot"] and not order["ledger"]
        assert order["snapshot"]["quote"]["amount"] == {
            "amount_minor": 100,
            "currency": "USD",
            "decimals": 2,
        }
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
            if not self.order(oid)["order"]["ledger"]:
                self.settle_review(recipe["id"], oid)
        else:
            # Preserve the unresolved/supported hold; never manufacture an answer
            # or approval to make this qualification look successful.
            save(self.output / (recipe["id"] + "-held.json"), current)
        save(self.output / (recipe["id"] + "-events.json"), self.page(run))
        return result

    def finish_held(self, label, run, oid):
        """Follow actual questions/controller actions; never insert a model disposition."""
        for index in range(3):
            page = self.page(run)
            view = self.order(oid)
            if view["order"]["ledger"]:
                break
            if view["order"]["cases"][-1]["status"] == "unsupported":
                self.settle_review(label, oid)
                break
            controller_ready = any(
                a["action"] == "approve" and a["enabled"] for a in page["available_actions"]
            )
            if page["evidence_request"] and not controller_ready:
                prior = view["order"]["cases"][-1]["questions_asked"]
                self.command(
                    f"/runs/{run}/answers",
                    {
                        "binding": page["binding"],
                        "request_id": page["evidence_request"]["request_id"],
                        "text": (
                            "I have no additional independent source records "
                            "or identity matching evidence."
                        ),
                        "references": [],
                    },
                    label + f":evidence-{index}",
                    repeat=True,
                )
                self.wait(
                    lambda: self.order(oid),
                    lambda v, previous=prior: (
                        bool(v["order"]["semantic_findings"])
                        and (
                            v["order"]["cases"][-1]["questions_asked"] > previous
                            or v["order"]["order_state"] == "human_review"
                            or v["order"]["cases"][-1]["status"] == "unsupported"
                        )
                    ),
                )
                continue
            assert any(a["action"] == "approve" and a["enabled"] for a in page["available_actions"])
            self.command(
                f"/runs/{run}/decisions",
                {
                    "binding": page["binding"],
                    "action": "approve",
                    "reason": (
                        "Simulated controller explicitly authorizes return of "
                        "uncaptured mock funds; no factual override."
                    ),
                    "evidence_ids": [],
                },
                label + ":controller-return",
                repeat=True,
            )
            self.wait(lambda: self.order(oid), lambda v: bool(v["order"]["ledger"]))
            break
        final = self.order(oid)
        assert len(final["order"]["ledger"]) == 1
        save(self.output / (label + "-final.json"), final)
        save(self.output / (label + "-events.json"), self.page(run))
        with sqlite3.connect(self.backend.app.state.orders.repository.path) as db:
            attempts = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT data FROM catalog_records WHERE kind='dataset_assessment'"
                )
                if json.loads(r[0])["order_id"] == oid
            ]
        save(self.output / (label + "-attempts.json"), attempts)


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


def child(root, recover=False, recovery_id=0):
    budget = configure()
    before_hash = source_hash()
    recipes = {
        "semantic-v1": SEMANTIC_CASES,
        "semantic-v2": FINAL_CASES,
        "semantic-v3": CONTEXT_CASES,
    }.get(root.name, RECIPES)
    complete_settlement = root.name.startswith("semantic-")
    training_batch = {"semantic-v1": 401, "semantic-v2": 501, "semantic-v3": 601}.get(
        root.name, 301
    )
    plan = {
        "lane": "LOCAL",
        "attempt": root.name,
        "recipes": recipes,
        "complete_settlement": complete_settlement,
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
        "criterion": (
            "Raw model and effective findings must both be correct and "
            "model-provenanced; deterministic fallback is not success"
        ),
        "artifact_contract": (
            "Actual HTTP commands/events, source/delivery bytes, raw model "
            "responses, persisted attempts, cumulative ledger reconciliation"
        ),
    }
    if recover:
        frozen = load(root / "frozen-plan.json")
        assert frozen["source_sha256"] == before_hash and frozen["recipes"] == list(recipes)
        save(
            root
            / (
                f"technical-recovery-{recovery_id}.json"
                if recovery_id > 1
                else "technical-recovery.json"
            ),
            {
                "runtime_unchanged": True,
                "harness_commit": plan["git_commit"],
                "cause": (
                    "Harness observed finding replacement incorrectly; "
                    "reuse completed assessments and retained question rounds"
                    if complete_settlement
                    else "Harness compared Money object to string"
                ),
            },
        )
    else:
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
            calls = (
                root / (f"recovery-calls-{recovery_id}" if recovery_id > 1 else "recovery-calls")
                if recover
                else root
            )
            if recover:
                calls.mkdir(exist_ok=False)
            observe(gateway, calls)
            journey = ConnectedJourney(client, root)
            if recover:
                source = load(root / "training-source.json")
                journey.anchor = datetime.fromisoformat(
                    source["partitions"][0]["authority"]["valid_until"]
                ) - timedelta(hours=24)
                for label in ("training", *(r["id"] for r in recipes)):
                    delivered = root / (label + "-delivered.json")
                    if not delivered.exists():
                        continue
                    order = load(delivered)["order"]
                    learning = load(root / (label + "-learning.json"))
                    journey.report["orders"][label] = {
                        "run_id": order["snapshot"]["quote"]["request_id"],
                        "order_id": order["snapshot"]["order_id"],
                        "snapshot_id": order["snapshot"]["snapshot_id"],
                        "source_bundle_id": learning["bundle_id"],
                        "initial_internal_reviews": 2 if label == "training" else 0,
                    }
                version = journey.learning()["active_version"]
            else:
                run, oid = journey.intake("training", training_batch, ambiguous=True)
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
            for batch, recipe in enumerate(recipes, training_batch + 1):
                if recipe["id"] in journey.report["orders"]:
                    info = journey.report["orders"][recipe["id"]]
                    run, oid = info["run_id"], info["order_id"]
                else:
                    run, oid = journey.intake(recipe["id"], batch)
                assert journey.report["orders"][recipe["id"]]["initial_internal_reviews"] == 0
                results.append(journey.assess(recipe, run, oid))
                if complete_settlement:
                    journey.finish_held(recipe["id"], run, oid)
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
            root
            / (
                f"recovery-failure-{recovery_id}.json"
                if recovery_id > 1
                else "recovery-failure.json"
                if recover
                else "failure.json"
            ),
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
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--recovery-id", type=int, default=0)
    args = parser.parse_args()
    if args.authorize:
        print(json.dumps(authorize(), indent=2))
        return
    if args.child:
        child(args.child, args.recover, args.recovery_id)
        return
    auth = load(AUTH)
    remaining = (datetime.fromisoformat(auth["cutoff"]) - datetime.now(UTC)).total_seconds()
    if remaining < 300:
        raise RuntimeError("Insufficient authorized time")
    if not args.cohort.replace("-", "").isalnum():
        raise ValueError("Use a simple new cohort identifier")
    root = OUTPUT / args.cohort
    if not args.recover:
        root.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC).isoformat()
    recovery_id = len(list(root.glob("recovery-supervisor*.json"))) + 1 if args.recover else 0
    prefix = (
        (f"recovery-supervisor-{recovery_id}" if recovery_id > 1 else "recovery-supervisor")
        if args.recover
        else "supervisor"
    )
    with (root / (prefix + ".log")).open("x", encoding="utf-8") as log:
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", str(root)]
                + (["--recover", "--recovery-id", str(recovery_id)] if args.recover else []),
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
        root / (prefix + ".json"),
        {"started": started, "ended": datetime.now(UTC).isoformat(), **result},
    )
    print(json.dumps({"evidence": str(root), **result}))


if __name__ == "__main__":
    main()
