"""Connected synthetic demonstration via the real frontend bridge and backend.

Supplies customer/owner/controller commands, never a verdict or learned answer.
Evidence is private, append-only per run; the independent audit is a separate tool.
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.learning_examples import example_bundle
from tools.local_learning_process import instance_state

ROOT = Path(__file__).resolve().parents[1]


def budget_snapshot(config):
    """Read the existing ledger, never register/refill a grant or load a key."""
    if not config.get("model_access"):
        return None
    path = Path(config["model_access"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != config["model_access_sha256"]:
        raise ValueError("Model access artifact changed after instance installation")
    access = json.loads(path.read_text(encoding="utf-8"))
    auth = access["authorization"]
    uri = Path(auth["ledger"]).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        count, active, cost, committed = db.execute(
            "SELECT count(*),coalesce(sum(status='RESERVED'),0),"
            "coalesce(sum(actual_micro_usd),0),"
            "coalesce(sum(coalesce(actual_micro_usd,reserved_micro_usd)),0) FROM calls"
        ).fetchone()
        reserve = db.execute("SELECT final_reserve_micro FROM allocation WHERE id=1").fetchone()[0]
    return {
        "requests": count,
        "active": active,
        "known_cost_usd": cost / 1e6,
        "committed_usd": committed / 1e6,
        "reserve_usd": reserve / 1e6,
        "maximum_usd": access["maximum_usd"],
        "model": auth["model"],
        "remaining_usd": float(access["maximum_usd"]) - (committed + reserve) / 1e6,
    }


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


class Journey:
    def __init__(self, instance, objection, owner_walkthroughs, after_restart_objection=None):
        self.state_dir = instance_state(instance)
        self.config = json.loads((self.state_dir / "launch.json").read_text(encoding="utf-8"))
        self.budget_before = budget_snapshot(self.config)
        if self.budget_before and self.budget_before["active"]:
            raise RuntimeError("Another model request is active; preserve its ownership")
        self.backend = httpx.Client(
            base_url=f"http://127.0.0.1:{self.config['backend_port']}", timeout=70
        )
        self.frontend_url = f"http://127.0.0.1:{self.config['frontend_port']}"
        self.frontend = httpx.Client(base_url=self.frontend_url, timeout=70)
        self.id = uuid4().hex
        self.output = self.state_dir / "evidence" / self.id
        self.output.mkdir(parents=True, exist_ok=False)
        self.anchor = datetime.now(UTC)
        self.owner_walkthroughs = json.loads(owner_walkthroughs.read_text(encoding="utf-8"))
        if self.owner_walkthroughs["origin"] != "explicitly_simulated_source_owner_training_input":
            raise ValueError("This demonstration requires explicitly simulated owner input")
        save(self.output / "owner-walkthroughs.json", self.owner_walkthroughs)
        self.retries = []
        self.report = {
            "id": self.id,
            "instance": instance,
            "started_at": self.anchor.isoformat(),
            "git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_tree_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True
                ).strip()
            ),
            "origin": "synthetic_sources_simulated_local_roles_mock_funding",
            "paid_calls": None if self.budget_before else 0,
            "model_mode": "real_provider" if self.budget_before else "offline",
            "budget_before": self.budget_before,
            "real_broadcasts": 0,
            "objection": objection,
            "after_restart_objection": after_restart_objection,
            "database": str(self.state_dir / "orders.sqlite3"),
            "orders": {},
            "profile": "aggregate-brokerage-v1",
            "frontend_url": self.frontend_url,
        }
        save(self.output / "report.json", self.report)

    def request(self, method, path, payload=None, *, key=None, bridge=True, expected=None):
        client = self.frontend if bridge else self.backend
        route = "/api/live" + path if bridge else path
        headers = {
            "Origin": self.frontend_url,
            "Idempotency-Key": key or self.id + ":" + uuid4().hex,
        }
        response = client.request(method, route, json=payload, headers=headers)
        try:
            body = response.json()
        except ValueError:
            body = {
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "bytes": len(response.content),
            }
        event = {
            "at": datetime.now(UTC).isoformat(),
            "method": method,
            "path": route,
            "bridge": bridge,
            "key": headers["Idempotency-Key"],
            "payload": payload,
            "status": response.status_code,
            "response": body,
        }
        with (self.output / "http-trace.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        if expected is not None:
            if response.status_code != expected:
                raise RuntimeError(
                    f"{route}: expected HTTP {expected}, observed {response.status_code}: {body}"
                )
        else:
            response.raise_for_status()
        return body

    def command(self, path, payload, label, *, repeat=False):
        key = self.id + ":" + label
        body = {**payload, "idempotency_key": key}
        # Run DTOs use the header; legacy/catalog and learning commands carry it.
        if path.startswith("/runs"):
            body.pop("idempotency_key")
        result = self.request("POST", path, body, key=key)
        if repeat:
            replay = self.request("POST", path, body, key=key)
            if replay != result:
                raise RuntimeError("exact command retry changed its saved response: " + path)
            self.retries.append({"path": path, "payload": body, "key": key, "response": result})
        return result

    def wait(self, read, predicate, *, seconds=45):
        cutoff = time.monotonic() + seconds
        while time.monotonic() < cutoff:
            value = read()
            if predicate(value):
                return value
            time.sleep(0.25)
        raise RuntimeError(
            "Required application state was not reached within the observation bound"
        )

    def page(self, run):
        after, events = 0, []
        while True:
            page = self.request("GET", f"/runs/{run}/events?after={after}&limit=100")
            events.extend(page["events"])
            if page["caught_up"]:
                return {**page, "events": events}
            if page["next_after"] <= after:
                raise RuntimeError("event cursor did not advance")
            after = page["next_after"]

    def learning(self):
        return self.request("GET", "/source-learning/state")

    def order(self, order_id):
        return self.request("GET", "/orders/" + order_id, bridge=False)

    @staticmethod
    def bound(view):
        return {
            "expected_revision": view["order"]["revision"],
            "expected_binding": view["order"]["binding"],
        }

    def source(self, label, batch, status="active"):
        bundle = example_bundle(self.anchor, batch).model_dump(mode="json")
        for part in bundle["partitions"]:
            if status == "expired":
                part["authority"]["valid_until"] = (self.anchor - timedelta(seconds=1)).isoformat()
            elif status != "active":
                part["authority"]["status"] = status
        save(self.output / (label + "-source.json"), bundle)
        return self.command("/source-learning/sources", bundle, label + ":sources")

    def intake(self, label, batch, *, ambiguous=False, status="active"):
        bundle = self.source(label, batch, status)
        prompt = (
            "SF adults 25-34 interested in fitness, counts by ZIP."
            if ambiguous
            else "SF adults 25-34, gym membership or fitness app use, counts by ZIP."
        )
        run = self.command(
            "/runs",
            {"prompt": prompt, "corpus_id": "sf-aggregate-v1"},
            label + ":create",
            repeat=True,
        )["id"]
        page = self.wait(lambda: self.page(run), lambda p: p["request"]["status"] != "compiling")
        reviews = [r for r in self.learning()["reviews"] if r["request_id"] == run]
        self.report["orders"][label] = {
            "run_id": run,
            "source_bundle_id": bundle["record_id"],
            "initial_internal_reviews": len(reviews),
        }
        if label == "training":
            # Explicit simulated source-owner testimony; the runtime derives its
            # procedures from these persisted application commands, not this driver.
            testimony = {
                item["source_family"]: item for item in self.owner_walkthroughs["walkthroughs"]
            }
            for review in reviews:
                self.command(
                    "/source-learning/resolve",
                    {
                        "encounter_id": review["encounter_id"],
                        "column": testimony[review["source_family"]]["column"],
                        "explanation": testimony[review["source_family"]]["explanation"],
                    },
                    "owner:" + review["source_family"],
                    repeat=True,
                )
            page = self.wait(
                lambda: self.page(run), lambda p: p["request"]["status"] != "compiling"
            )
        if page["request"]["status"] == "clarification":
            draft = page["request"]
            self.command(
                f"/requests/{run}/answers",
                {
                    "expected_revision": draft["revision"],
                    "question_id": draft["question"]["question_id"],
                    "text": "Gym membership or fitness-app use; exclude standalone yoga.",
                },
                label + ":clarify",
                repeat=True,
            )
            page = self.wait(
                lambda: self.page(run), lambda p: p["request"]["status"] != "compiling"
            )
        save(self.output / (label + "-intake.json"), page)
        if status != "active":
            self.report["orders"][label]["held_status"] = page["request"]["status"]
            save(self.output / (label + "-learning.json"), self.learning())
            return run, None
        if page["request"]["status"] != "ready":
            raise RuntimeError("intake not ready: " + str(page["request"].get("error")))
        quote = self.command(
            f"/requests/{run}/quotes",
            {"expected_revision": page["request"]["revision"]},
            label + ":quote",
            repeat=True,
        )
        save(self.output / (label + "-quote.json"), quote)
        view = self.command(
            "/quote-acceptance",
            {"quote_id": quote["quote_id"], "customer_actor": "simulated:Summit-demo-buyer"},
            label + ":accept-contract",
            repeat=True,
        )
        oid = view["order"]["snapshot"]["order_id"]
        save(self.output / (label + "-unfunded.json"), view)
        prep = self.command(
            f"/orders/{oid}/funding-preparation",
            self.bound(view),
            label + ":prepare-funding",
            repeat=True,
        )
        self.command(
            f"/orders/{oid}/funding-authorizations",
            {
                **self.bound(view),
                "funding_attempt_id": prep["funding_attempt_id"],
                "payment_hash": prep["terms"]["payment_hash"],
                "simulate": True,
            },
            label + ":fund",
            repeat=True,
        )
        view = self.wait(
            lambda: self.order(oid),
            lambda v: (
                bool(v["order"]["deliveries"])
                or v["order"]["order_state"] in ("human_review", "operational_failure")
            ),
        )
        if not view["order"]["deliveries"]:
            raise RuntimeError(
                "fulfillment did not produce a delivery: " + str(view["order"].get("error"))
            )
        self.report["orders"][label].update(
            order_id=oid, snapshot_id=view["order"]["snapshot"]["snapshot_id"]
        )
        save(self.output / (label + "-delivered.json"), view)
        for name in ("csv", "preview"):
            artifact = view["order"]["deliveries"][-1][name]
            response = self.backend.get(f"/orders/{oid}/artifacts/{artifact['artifact_id']}")
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != artifact["sha256"]:
                raise RuntimeError("download hash differs from recorded delivery")
            (self.output / f"{label}-delivery.{'csv' if name == 'csv' else 'json'}").write_bytes(
                response.content
            )
        save(self.output / (label + "-learning.json"), self.learning())
        return run, oid

    def settle_review(self, label, oid):
        view = self.order(oid)
        self.command(
            f"/orders/{oid}/acceptance", self.bound(view), label + ":review-accept", repeat=True
        )
        final = self.wait(lambda: self.order(oid), lambda v: bool(v["order"]["ledger"]))
        save(self.output / (label + "-final.json"), final)
        save(
            self.output / (label + "-payment-justification.json"),
            self.request("GET", f"/orders/{oid}/payment-justification"),
        )

    def dispute(self, label, run, oid, text, *, field=None, intent="dispute_fact"):
        page, view = self.page(run), self.order(oid)
        target = next((t for t in page["complaint_targets"] if t["field"] == field), None)
        stale = page["binding"]
        self.command(
            f"/orders/{oid}/{'disputes' if target else 'complaints'}",
            (
                {
                    **self.bound(view),
                    "complaint": {
                        "text": text,
                        "field": field,
                        "intent": intent,
                        "requirement_id": target["requirement_id"],
                        "product_id": "dataset",
                        "artifact_id": view["order"]["deliveries"][-1]["csv"]["artifact_id"],
                    },
                }
                if target
                else {**self.bound(view), "text": text}
            ),
            label + ":dispute",
            repeat=True,
        )
        if intent == "change_scope":
            final = self.wait(
                lambda: self.order(oid), lambda v: v["order"]["cases"][-1]["status"] != "open"
            )
            save(self.output / (label + "-disposition.json"), final)
            self.settle_review(label, oid)
            return
        for index in range(3):
            observed = self.wait(
                lambda: {"page": self.page(run), "view": self.order(oid)},
                lambda p: (
                    p["page"]["evidence_request"] is not None
                    or any(
                        a["action"] == "approve" and a["enabled"]
                        for a in p["page"]["available_actions"]
                    )
                    or p["view"]["order"]["cases"][-1]["status"] in {"unsupported", "answered"}
                ),
            )
            page = observed["page"]
            if observed["view"]["order"]["cases"][-1]["status"] in {"unsupported", "answered"}:
                save(self.output / (label + "-disposition.json"), observed["view"])
                self.settle_review(label, oid)
                return
            save(self.output / f"{label}-investigation-{index}.json", page)
            if page["evidence_request"]:
                self.command(
                    f"/runs/{run}/answers",
                    {
                        "binding": page["binding"],
                        "request_id": page["evidence_request"]["request_id"],
                        "text": (
                            "I have no cross-ZIP identity records or separate source "
                            "evidence supporting this allegation."
                        ),
                        "references": [],
                    },
                    label + f":answer-{index}",
                    repeat=True,
                )
                continue
            self.request(
                "POST",
                f"/runs/{run}/decisions",
                {
                    "action": "approve",
                    "binding": stale,
                    "reason": "Deliberately obsolete binding; this must not authorize settlement.",
                    "evidence_ids": [],
                },
                key=self.id + ":stale-decision",
                expected=409,
            )
            save(self.output / (label + "-held.json"), self.order(oid))
            self.command(
                f"/runs/{run}/decisions",
                {
                    "action": "approve",
                    "binding": page["binding"],
                    "reason": (
                        "Explicit simulated controller approval to return uncaptured mock "
                        "funds for this unresolved order; no factual override."
                    ),
                    "evidence_ids": [],
                },
                label + ":return",
                repeat=True,
            )
            final = self.wait(lambda: self.order(oid), lambda v: bool(v["order"]["ledger"]))
            save(self.output / (label + "-final.json"), final)
            return
        raise RuntimeError("bounded investigation did not expose an authorized disposition")

    def run(self):
        if self.learning()["bundle_id"]:
            raise RuntimeError(
                "Use a fresh launcher instance/database; existing evidence is never reset"
            )
        for path in ("/", "/live", "/api/broker-run/health"):
            response = self.frontend.get(path)
            response.raise_for_status()
            self.report.setdefault("routes", {})[path] = response.status_code
        response = self.frontend.post(
            "/api/broker-run/runs", json={"case": "shared"}, headers={"Origin": self.frontend_url}
        )
        response.raise_for_status()
        compatibility = response.json()["id"]
        self.report["compatibility_probe"] = {
            "handle": compatibility,
            "notice": "Separate retained broker profile; not aggregate learning proof",
        }
        page = self.wait(
            lambda: self.frontend.get(
                f"/api/broker-run/runs/{compatibility}/events?after=0"
            ).json(),
            lambda p: bool(p.get("events")),
        )
        save(self.output / "compatibility-events.json", page)
        run, oid = self.intake("training", 101, ambiguous=True)
        self.settle_review("training", oid)
        bundle = self.learning()["bundle_id"]
        candidate = self.command("/source-learning/propose", {"target_id": bundle}, "propose")[
            "record_id"
        ]
        self.command("/source-learning/qualify", {"target_id": candidate}, "qualify", repeat=True)
        version = self.command("/source-learning/approve", {"target_id": candidate}, "approve")[
            "record_id"
        ]
        self.command("/source-learning/activate", {"target_id": version}, "activate", repeat=True)
        self.report["learning_version"] = version
        run, oid = self.intake("later", 102)
        self.dispute("later", run, oid, self.report["objection"])
        before = self.order(oid)
        self.report["process_before"] = json.loads(
            (self.state_dir / "backend-process.json").read_text()
        )
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-File",
                str(ROOT / "tools/local_learning.ps1"),
                "-Action",
                "RestartBackend",
                "-Instance",
                self.config["instance"],
                "-BackendPort",
                str(self.config["backend_port"]),
                "-FrontendPort",
                str(self.config["frontend_port"]),
                *(
                    ["-ModelAccess", self.config["model_access"]]
                    if self.config.get("model_access")
                    else []
                ),
            ],
            cwd=ROOT,
            check=True,
            timeout=45,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        cutoff = time.monotonic() + 30
        while True:
            try:
                if self.backend.get("/health").is_success:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= cutoff:
                raise RuntimeError("restarted backend unavailable")
            time.sleep(0.25)
        self.report["process_after"] = json.loads(
            (self.state_dir / "backend-process.json").read_text()
        )
        after = self.order(oid)
        save(self.output / "later-after-restart.json", after)
        if before["order"] != after["order"]:
            raise RuntimeError("settled order state changed across restart")
        for retry in self.retries:
            if (
                self.request("POST", retry["path"], retry["payload"], key=retry["key"])
                != retry["response"]
            ):
                raise RuntimeError("saved response did not survive restart")
        self.report["retries_after_restart"] = len(self.retries)
        run, oid = self.intake("after-restart", 103)
        if self.report.get("after_restart_objection"):
            self.dispute("after-restart", run, oid, self.report["after_restart_objection"])
        else:
            self.settle_review("after-restart", oid)
        run, oid = self.intake("scope-change", 104)
        self.dispute(
            "scope-change",
            run,
            oid,
            "Add Oakland residents and standalone yoga to this accepted "
            "SF gym/app dataset at no extra charge.",
            field="category",
            intent="change_scope",
        )
        for index, status in enumerate(("conflict", "revoked", "expired"), 105):
            self.intake(status, index, status=status)
        for label, info in self.report["orders"].items():
            save(self.output / (label + "-events.json"), self.page(info["run_id"]))
            if info.get("order_id"):
                save(self.output / (label + "-current.json"), self.order(info["order_id"]))
                save(
                    self.output / (label + "-payment-justification.json"),
                    self.request("GET", f"/orders/{info['order_id']}/payment-justification"),
                )
        save(self.output / "final-learning.json", self.learning())
        self.report["completed_at"] = datetime.now(UTC).isoformat()
        self.report["completed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", required=True)
    parser.add_argument(
        "--owner-walkthroughs",
        type=Path,
        default=ROOT / "docs/examples/judge-owner-walkthroughs.json",
    )
    parser.add_argument(
        "--objection",
        default=(
            "People using gym apps and yoga may be counted twice across ZIPs; "
            "show cross-ZIP deduplication evidence."
        ),
    )
    parser.add_argument(
        "--after-restart-objection",
        help="Optional fresh complaint on the independent post-restart order",
    )
    args = parser.parse_args()
    journey = Journey(
        args.instance, args.objection, args.owner_walkthroughs, args.after_restart_objection
    )
    try:
        journey.run()
    except Exception as error:
        journey.report.update(completed=False, failure=f"{type(error).__name__}: {error}")
        raise
    finally:
        if journey.budget_before:
            after = budget_snapshot(journey.config)
            journey.report["budget_after"] = after
            journey.report["paid_calls"] = after["requests"] - journey.budget_before["requests"]
            journey.report["new_known_cost_usd"] = (
                after["known_cost_usd"] - journey.budget_before["known_cost_usd"]
            )
            journey.report["accounting_note"] = (
                "Shared-ledger delta; verify per-request traces "
                "before attributing all calls to this journey."
            )
        save(journey.output / "report.json", journey.report)
        print(
            json.dumps(
                {"output": str(journey.output), "completed": journey.report.get("completed", False)}
            )
        )


if __name__ == "__main__":
    main()
