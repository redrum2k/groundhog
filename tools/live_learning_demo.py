"""Ordinary HTTP acceptance driver; owner/controller interactions happen in /live.

All identities and source examples are simulated. No rule injection, private eval
labels in runtime, paid calls, live funding or preconstructed playback events.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.learning_examples import example_bundle

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/live-learning"
URL = "http://127.0.0.1:8026"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


class Demo:
    def __init__(self, directory):
        self.directory = directory
        self.session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        self.credentials = json.loads((LOCAL / "demo-credentials.json").read_text(encoding="utf-8"))
        self.trace = (
            json.loads((directory / "http-trace.json").read_text(encoding="utf-8"))
            if (directory / "http-trace.json").exists()
            else []
        )
        self.client = httpx.Client(base_url=URL, timeout=45)

    def request(self, method, path, payload=None, role=None, key=None):
        headers = {}
        if role == "worker":
            headers["X-Internal-Token"] = self.credentials["INTERNAL_API_TOKEN"]
        if method == "POST":
            headers["Idempotency-Key"] = key or payload.get(
                "idempotency_key", self.session["id"] + path
            )
        response = self.client.request(method, path, json=payload, headers=headers)
        try:
            body = response.json()
        except ValueError:
            body = {"bytes_sha256": hashlib.sha256(response.content).hexdigest()}
        self.trace.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "path": path,
                "status": response.status_code,
                "response": body,
            }
        )
        save(self.directory / "http-trace.json", self.trace)
        response.raise_for_status()
        return body

    def state(self):
        return self.request("GET", "/source-learning/state", role="worker")

    def wait(self, path, predicate):
        cutoff = time.monotonic() + 40
        while time.monotonic() < cutoff:
            value = self.request("GET", path)
            if predicate(value):
                return value
            time.sleep(0.25)
        raise RuntimeError("Application did not reach the required state: " + path)

    def new_request(self, label, batch, *, conflict=False):
        source = example_bundle(
            datetime.fromisoformat(self.session["anchor"]),
            batch + self.session.get("start_batch", 1) - 1,
            conflict=conflict,
        )
        source = source.model_copy(
            update={"idempotency_key": self.session["id"] + ":source:" + label}
        )
        save(self.directory / (label + "-source.json"), source.model_dump(mode="json"))
        self.request("POST", "/source-learning/sources", source.model_dump(mode="json"), "worker")
        created = self.request(
            "POST",
            "/runs",
            {
                "prompt": "SF adults 25-34, gym membership or fitness app use, counts by ZIP.",
                "corpus_id": "sf-aggregate-v1",
            },
            key=self.session["id"] + ":create:" + label,
        )
        self.session[label] = created["id"]
        save(self.directory / "session.json", self.session)
        return created["id"]

    def finish(self, label):
        request = self.session[label]
        draft = self.wait(
            "/requests/" + request, lambda r: r["status"] in ("ready", "human_review")
        )
        if draft["status"] != "ready":
            raise RuntimeError("Unexpected source review: " + str(draft.get("error")))
        prefix = self.session["id"] + ":" + label
        quote = self.request(
            "POST",
            f"/requests/{request}/quotes",
            {
                "expected_revision": draft["revision"],
                "idempotency_key": prefix + ":quote",
            },
        )
        assert quote["amount"]["amount_minor"] == 12000
        view = self.request(
            "POST",
            "/quote-acceptance",
            {
                "quote_id": quote["quote_id"],
                "customer_actor": "simulated:AcmeFitness-demo-buyer",
                "idempotency_key": prefix + ":accept",
            },
        )
        order = view["order"]
        order_id = order["snapshot"]["order_id"]
        assert not order["deliveries"] and order["authorization"]["status"] == "pending"
        bound = {"expected_revision": order["revision"], "expected_binding": order["binding"]}
        preparation = self.request(
            "POST",
            f"/orders/{order_id}/funding-preparation",
            {**bound, "idempotency_key": prefix + ":prepare"},
        )
        self.request(
            "POST",
            f"/orders/{order_id}/funding-authorizations",
            {
                **bound,
                "idempotency_key": prefix + ":fund",
                "funding_attempt_id": preparation["funding_attempt_id"],
                "payment_hash": preparation["terms"]["payment_hash"],
                "simulate": True,
            },
        )
        view = self.wait("/orders/" + order_id, lambda v: bool(v["order"]["deliveries"]))
        order = view["order"]
        assert order["verification"]["passed"] and view["payment"]["simulated"]
        artifact = order["deliveries"][-1]["csv"]
        response = self.client.get(f"/orders/{order_id}/artifacts/{artifact['artifact_id']}")
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
        (self.directory / (label + "-delivery.csv")).write_bytes(response.content)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        supplied = json.loads(
            (self.directory / (label + "-source.json")).read_text(encoding="utf-8")
        )
        # Fixture semantics, kept outside runtime: independent literal byte oracle.
        columns = {"local-demo-partition-0": "v_count", "local-demo-partition-1": "p_adults"}
        expected = {
            row["zip"]: (
                str(row["values"][columns[p["export"]["source_family"]]])
                if row["status"] == "released"
                else "",
                row["status"],
            )
            for p in supplied["partitions"]
            for row in p["export"]["rows"]
        }
        assert len(rows) == len(expected)
        assert {r["zip"]: (r["count"], r["status"]) for r in rows} == expected
        events = self.request("GET", f"/runs/{request}/events?after=0&limit=100")
        save(self.directory / (label + "-events.json"), events)
        save(self.directory / (label + "-order.json"), view)
        result = {
            "request_id": request,
            "order_id": order_id,
            "csv_sha256": artifact["sha256"],
            "independently_verified_rows": len(rows),
            "explicit_acceptance": True,
            "mock_funding": True,
        }
        self.session[label + "_result"] = result
        save(self.directory / "session.json", self.session)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("prepare", "finish-training", "later", "after-restart", "conflict", "status"),
    )
    parser.add_argument("--session", type=Path)
    parser.add_argument("--start-batch", type=int, default=1)
    args = parser.parse_args()
    if args.phase == "prepare":
        identifier = uuid4().hex
        directory = LOCAL / "evidence" / identifier
        directory.mkdir(parents=True, exist_ok=False)
        save(
            directory / "session.json",
            {
                "id": identifier,
                "anchor": datetime.now(UTC).isoformat(),
                "start_batch": args.start_batch,
                "initial_process": json.loads(
                    (LOCAL / "backend-process.json").read_text(encoding="utf-8")
                ),
                "origin": "controlled_local_synthetic_demonstration",
                "paid_calls": 0,
            },
        )
    else:
        if not args.session:
            parser.error("--session must identify the preserved prepare directory")
        directory = args.session.resolve()
        if not directory.is_relative_to(LOCAL.resolve()):
            parser.error("session must be inside the project-owned local demo directory")
    demo = Demo(directory)
    if args.phase == "prepare":
        assert demo.request("GET", "/health")["payment_mode"] == "mock"
        request = demo.new_request("training", 1)
        demo.wait("/requests/" + request, lambda r: r["status"] == "human_review")
        result = {
            "session": str(directory),
            "request_id": request,
            "next": (
                "Use /live Source learning to resolve v_count and p_adults "
                "with explicit simulated-owner explanations."
            ),
        }
    elif args.phase == "finish-training":
        result = demo.finish("training")
    elif args.phase in ("later", "after-restart"):
        state = demo.state()
        assert state["active_version"]
        if args.phase == "after-restart":
            process = json.loads((LOCAL / "backend-process.json").read_text(encoding="utf-8"))
            assert process["wrapper_pid"] != demo.session["initial_process"]["wrapper_pid"]
            assert state["active_version"] == demo.session["active_version"]
            demo.session["restarted_process"] = process
        demo.session["active_version"] = state["active_version"]
        demo.new_request(args.phase, 2 if args.phase == "later" else 3)
        result = demo.finish(args.phase)
        state = demo.state()
        assert not [r for r in state["reviews"] if r["request_id"] == result["request_id"]]
        result["internal_reviews"] = 0
        attempt = next(
            a for a in reversed(state["attempts"]) if a["request_id"] == result["request_id"]
        )
        assert attempt["baseline_reviews"] == 2 and attempt["internal_reviews"] == 0
        result["same_byte_comparison"] = attempt
        save(directory / (args.phase + "-learning-state.json"), state)
    elif args.phase == "conflict":
        request = demo.new_request("conflict", 4, conflict=True)
        held = demo.wait("/requests/" + request, lambda r: r["status"] == "human_review")
        state = demo.state()
        reviews = [r for r in state["reviews"] if r["request_id"] == request]
        assert len(reviews) == 2 and all(r["reason"] == "authority_conflict" for r in reviews)
        assert held["order_id"] is None
        result = {
            "request_id": request,
            "counterexample": "authority_conflict",
            "blocked": True,
            "accepted_order": None,
        }
        save(directory / "conflict-learning-state.json", state)
    else:
        result = demo.state()
    save(directory / (args.phase + "-result.json"), result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
