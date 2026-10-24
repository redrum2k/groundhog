"""Real localhost Next→broker round trip, NOT a claimed visual browser test."""

import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend/artifacts/dispute-followup/browser"
URL = "http://127.0.0.1:3108"


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        URL + path, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def counts():
    with sqlite3.connect(OUT / "orders.sqlite3") as db:
        return {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("br_orders", "jf_events", "br_assessment_attempts", "jf_model_calls")
        }


def main():
    if (OUT / "http-check.json").exists():
        raise RuntimeError("Existing smoke evidence; no automatic replay")
    result = {
        "browser_status": "BLOCKED: no browser provider is available",
        "feature_enabled": False,
        "models_enabled": False,
        "checks": {},
    }
    for path in ("/", "/jobflow", "/catalog"):
        status, _ = request(path)
        result["checks"][path] = status
    status, body = request("/api/broker-run/runs", {"case": "shared"})
    result["create_status"] = status
    run = json.loads(body)
    result["run"] = run
    started = time.monotonic()
    events = []
    if status == 200 and "id" in run:
        endpoint = f"/api/broker-run/runs/{run['id']}/events?after=0"
        while time.monotonic() - started < 55:
            status, body = request(endpoint)
            value = json.loads(body)
            events = value.get("events", [])
            if any(e.get("type") == "run_finished" for e in events) or value.get("done"):
                break
            time.sleep(1)
        before = counts()
        for _ in range(3):
            request(endpoint)
        result["repeated_read_counts_before"] = before
        result["repeated_read_counts_after"] = counts()
    result["elapsed_seconds"] = time.monotonic() - started
    result["events"] = events
    with sqlite3.connect(OUT / "orders.sqlite3") as db:
        result["orders"] = [json.loads(row[0]) for row in db.execute("SELECT body FROM br_orders")]
    (OUT / "http-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"events", "orders"}}, indent=2))


if __name__ == "__main__":
    main()
