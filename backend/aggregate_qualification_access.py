"""Explicit 90-minute authorization; preserve every earlier window and dollar."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.agents.budget import ModelBudget

WINDOW = "aggregate-qualification-20261024"
# Conservatively rounded down from the first observed receipt-time clock (12:52:17).
START = "2026-10-24T12:52:00-07:00"
CUTOFF = "2026-10-24T14:22:00-07:00"
LEDGER = Path("D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3")
AUTHORIZATION = Path(
    "C:/Users/sajee/.codex/attachments/47e1b17b-fa36-4396-b499-1e3701137bfd/pasted-text-1.txt"
)
OUTPUT = Path(__file__).parent / "artifacts/aggregate-qualification-20261024"


def configured_window():
    if not LEDGER.is_file():
        raise RuntimeError("Existing cumulative ledger is required; never create a replacement")
    if Path(os.environ["APPLICATION_MODEL_BUDGET_PATH"]).resolve() != LEDGER.resolve():
        raise RuntimeError("Qualification must retain the cumulative ledger")
    if os.environ.get("CLAUDE_MODEL") != "claude-opus-5-5":
        raise RuntimeError("Use the configured approved Claude model")
    # Process-local settings only. No .env, shared server or production mutation.
    os.environ["ENABLE_PAID_MODELS"] = "true"
    os.environ["APPLICATION_MODEL_WINDOW_ID"] = WINDOW
    os.environ["APPLICATION_MODEL_CUTOFF_AT"] = CUTOFF
    return ModelBudget.configured()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "authorization.json"
    if target.exists():
        raise RuntimeError("Authorization receipt already exists; inspect it, never overwrite")
    if not LEDGER.is_file():
        raise RuntimeError("Missing existing ledger")
    if Path(os.environ["APPLICATION_MODEL_BUDGET_PATH"]).resolve() != LEDGER.resolve():
        raise RuntimeError("Wrong ledger")
    original = ModelBudget(LEDGER, cutoff=CUTOFF)
    before = original.summary()
    digest = hashlib.sha256(AUTHORIZATION.read_bytes()).hexdigest()
    original.register_authorized_window(
        WINDOW, starts_at=START, cutoff=CUTOFF, authorization_sha256=digest
    )
    current = configured_window()
    receipt = dict(
        window=WINDOW,
        start=START,
        cutoff=CUTOFF,
        start_basis="Receipt minute rounded down; no extension beyond 90 minutes",
        authorization_sha256=digest,
        before=before,
        after=current.summary(),
        registered_at=datetime.now(UTC).isoformat(),
    )
    with target.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
