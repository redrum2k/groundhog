import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.contracts.api import OrderRecord


class OrderRepository:
    """One SQLite transaction owns each version check, transition, and mock booking."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS order_commands (order_id TEXT NOT NULL, "
                "idempotency_key TEXT NOT NULL, request TEXT NOT NULL, response TEXT NOT NULL, "
                "PRIMARY KEY (order_id, idempotency_key))"
            )

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, order_id: str) -> OrderRecord | None:
        row = db.execute("SELECT data FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return OrderRecord.model_validate_json(row[0]) if row else None

    @staticmethod
    def save(db, order: OrderRecord) -> None:
        db.execute(
            "INSERT INTO orders VALUES (?, ?) "
            "ON CONFLICT(order_id) DO UPDATE SET data=excluded.data",
            (order.snapshot.order_id, order.model_dump_json()),
        )
