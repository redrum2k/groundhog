import sqlite3
from pathlib import Path


class MockPaymentJournal:
    """Durable local mock deduplication; not a live transaction executor/outbox."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS mock_operations ("
                "idempotency_key TEXT PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL)"
            )

    def record(self, key: str, request: str, receipt: str) -> str:
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO mock_operations VALUES (?, ?, ?)", (key, request, receipt)
            )
            stored_request, stored_receipt = self._connection.execute(
                "SELECT request, receipt FROM mock_operations WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if stored_request != request:
                raise ValueError(
                    "idempotency key already used for a different operation or payload"
                )
            return stored_receipt

    def lookup(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT receipt FROM mock_operations WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._connection.close()
