"""Explicit additive authorization for the separately requested primary follow-up."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.agents.budget import ModelBudget

WINDOW = "primary-semantic-followup-20261024"
START = "2026-10-24T11:19:36-07:00"
CUTOFF = "2026-10-24T12:25:38-07:00"
LEDGER = Path("D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3")
AUTHORIZATION = Path(
    "C:/Users/sajee/.codex/attachments/9d67041c-519c-45cc-93d5-c0d0d94c83be/pasted-text-1.txt"
)
OUTPUT = Path(__file__).parent / "artifacts/primary-followup"


def configured_window():
    if Path(os.environ["APPLICATION_MODEL_BUDGET_PATH"]).resolve() != LEDGER.resolve():
        raise RuntimeError("Primary follow-up must retain the cumulative ledger")
    os.environ["APPLICATION_MODEL_WINDOW_ID"] = WINDOW
    os.environ["APPLICATION_MODEL_CUTOFF_AT"] = CUTOFF
    return ModelBudget.configured()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "authorization.json"
    if target.exists():
        raise RuntimeError("Authorization receipt already exists; inspect, do not replace")
    budget = ModelBudget.configured()
    if budget.path.resolve() != LEDGER.resolve():
        raise RuntimeError("Wrong cumulative ledger")
    before = budget.summary()
    digest = hashlib.sha256(AUTHORIZATION.read_bytes()).hexdigest()
    budget.register_authorized_window(
        WINDOW, starts_at=START, cutoff=CUTOFF, authorization_sha256=digest
    )
    receipt = dict(
        window=WINDOW,
        start=START,
        cutoff=CUTOFF,
        authorization_sha256=digest,
        before=before,
        after=configured_window().summary(),
        registered_at=datetime.now(UTC).isoformat(),
    )
    with target.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
