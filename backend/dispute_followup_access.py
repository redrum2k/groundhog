"""Explicit follow-up authorization and a guarded connectivity check; never prints secrets."""

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.agents.bounded_client import BoundedClient
from app.agents.budget import ModelBudget

WINDOW = "broker-dispute-followup-20261024"
START = "2026-10-24T10:25:38-07:00"
CUTOFF = "2026-10-24T12:25:38-07:00"
LEDGER = Path("D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3")
AUTHORIZATION = Path(
    "C:/Users/sajee/.codex/attachments/5ee9cf69-30ef-4a7c-88c2-f89aca82f8c9/pasted-text-1.txt"
)
OUTPUT = Path(__file__).parent / "artifacts/dispute-followup"


def configured_window():
    if Path(os.environ["APPLICATION_MODEL_BUDGET_PATH"]).resolve() != LEDGER.resolve():
        raise RuntimeError("Follow-up must use the existing cumulative V6 ledger")
    os.environ["APPLICATION_MODEL_WINDOW_ID"] = WINDOW
    os.environ["APPLICATION_MODEL_CUTOFF_AT"] = CUTOFF
    return ModelBudget.configured()


def save(name, data):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / name
    # Evidence is append-only at the experiment level: no silent rerolls/overwrites.
    with target.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "authorize", "smoke"])
    action = parser.parse_args().action
    if action == "status":
        budget = ModelBudget.configured()
        print(
            json.dumps(
                {
                    "key_present": bool(os.getenv("ANTHROPIC_API_KEY")),
                    "model": os.getenv("CLAUDE_MODEL"),
                    "enabled": os.getenv("ENABLE_PAID_MODELS"),
                    "ledger": str(budget.path),
                    "summary": budget.summary(),
                },
                indent=2,
            )
        )
        return
    if action == "authorize":
        budget = ModelBudget.configured()
        if budget.path.resolve() != LEDGER.resolve():
            raise RuntimeError("Wrong cumulative ledger")
        before = budget.summary()
        ledger_hash = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
        authorization_hash = hashlib.sha256(AUTHORIZATION.read_bytes()).hexdigest()
        budget.register_authorized_window(
            WINDOW, starts_at=START, cutoff=CUTOFF, authorization_sha256=authorization_hash
        )
        current = configured_window()
        receipt = {
            "window": WINDOW,
            "start": START,
            "cutoff": CUTOFF,
            "original_ledger_sha256": ledger_hash,
            "authorization_sha256": authorization_hash,
            "before": before,
            "after": current.summary(),
            "registered_at": datetime.now(UTC).isoformat(),
        }
        save("authorization.json", receipt)
        print(json.dumps(receipt, indent=2))
        return
    budget = configured_window()
    if (OUTPUT / "smoke.json").exists():
        raise RuntimeError("Smoke evidence already exists; no implicit repeat")
    before = budget.summary()
    client = BoundedClient(purpose="dispute-followup-smoke", budget=budget)
    record = {"started_at": datetime.now(UTC).isoformat(), "before": before}
    started = time.monotonic()

    class Output(BaseModel):
        ok: bool

    try:
        available = client.client.models.retrieve(os.environ["CLAUDE_MODEL"])
        record["available_model_id"] = available.id
        response = client.parse(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=256,
            output_format=Output,
            messages=[{"role": "user", "content": "Return ok=true."}],
        )
        record.update(
            success=response.stop_reason == "end_turn" and response.parsed_output.ok,
            actual_model=client.last_response["model"],
            raw_response=client.last_response,
            call_id=client.last_call_id,
        )
    except Exception as error:
        record.update(
            success=False,
            error_type=type(error).__name__,
            status_code=getattr(error, "status_code", None),
            raw_response=client.last_response,
            call_id=client.last_call_id,
        )
    finally:
        record["latency_seconds"] = time.monotonic() - started
        record["after"] = budget.summary()
        record["estimated_cost_usd"] = round(
            record["after"]["known_cost_usd"] - before["known_cost_usd"], 6
        )
        client.close()
        save("smoke.json", record)
    print(json.dumps({k: v for k, v in record.items() if k != "raw_response"}, indent=2))


if __name__ == "__main__":
    main()
