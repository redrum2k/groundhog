import os
from pathlib import Path

from app.payments.mock import MockPaymentAdapter


def configured_payment_mode() -> str:
    mode = os.getenv("PAYMENT_ADAPTER", "mock")
    if mode != "mock":
        raise ValueError(
            "only PAYMENT_ADAPTER=mock is implemented; complete the payment spike first"
        )
    return mode


def get_payment_adapter(journal_path: Path | None = None) -> MockPaymentAdapter:
    configured_payment_mode()
    path = (
        journal_path
        if journal_path is not None
        else Path(os.getenv("MOCK_PAYMENT_DB_PATH", "artifacts/mock-payments.sqlite3"))
    )
    return MockPaymentAdapter(path)
