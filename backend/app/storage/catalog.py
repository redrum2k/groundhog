"""Additive schema migration: v0.2 orders and command responses remain byte-for-byte intact."""

import json

from app.orders.service import DomainError
from app.storage.orders import OrderRepository


class CatalogRepository(OrderRepository):
    def __init__(self, path):
        super().__init__(path)
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_records (kind TEXT, id "
                "TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_commands (scope TEXT, "
                "key TEXT, fingerprint TEXT NOT NULL, response TEXT NOT "
                "NULL, PRIMARY KEY(scope,key))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_sources (source_id TEXT, "
                "version INTEGER, selectable INTEGER NOT NULL, data TEXT NOT "
                "NULL, PRIMARY KEY(source_id,version))"
            )
            db.execute("INSERT OR IGNORE INTO schema_migrations VALUES (3)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_run_events ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, "
                "digest TEXT NOT NULL, data TEXT NOT NULL)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS catalog_run_cursor ON catalog_run_events(run_id,seq)"
            )

    @staticmethod
    def load(db, kind, identifier, model):
        row = db.execute(
            "SELECT data FROM catalog_records WHERE kind=? AND id=?", (kind, identifier)
        ).fetchone()
        if not row:
            raise DomainError(404, f"{kind} not found")
        return model.model_validate_json(row[0])

    @staticmethod
    def put(db, kind, identifier, value):
        db.execute(
            (
                "INSERT INTO catalog_records VALUES (?,?,?) ON "
                "CONFLICT(kind,id) DO UPDATE SET data=excluded.data"
            ),
            (kind, identifier, value.model_dump_json()),
        )

    @staticmethod
    def all(db, kind, model):
        return [
            model.model_validate_json(row[0])
            for row in db.execute(
                "SELECT data FROM catalog_records WHERE kind=? ORDER BY id", (kind,)
            ).fetchall()
        ]

    @staticmethod
    def replay(db, scope, key, fingerprint, model):
        row = db.execute(
            "SELECT fingerprint,response FROM catalog_commands WHERE scope=? AND key=?",
            (scope, key),
        ).fetchone()
        if row:
            if row[0] != fingerprint:
                raise DomainError(409, "idempotency key reused with changed request")
            return model.model_validate_json(row[1])
        return None

    @staticmethod
    def remember(db, scope, key, fingerprint, response):
        db.execute(
            "INSERT INTO catalog_commands VALUES (?,?,?,?)",
            (scope, key, fingerprint, response.model_dump_json()),
        )

    @staticmethod
    def fingerprint(operation, command):
        return json.dumps(
            {"operation": operation, "payload": command.model_dump(mode="json")}, sort_keys=True
        )
