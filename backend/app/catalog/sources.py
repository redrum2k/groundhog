import sqlite3

from app.contracts.catalog import Source
from app.orders.service import DomainError


class SourceRegistry:
    def __init__(self, repository, store):
        self.repository, self.store = repository, store

    def register(self, source: Source, *, selectable=True, db=None):
        self.store.read(source.artifact)
        if db is None:
            with self.repository.transaction() as connection:
                return self.register(source, selectable=selectable, db=connection)
        if db is not None:
            row = db.execute(
                "SELECT data FROM catalog_sources WHERE source_id=? AND version=?",
                (source.source_id, source.version),
            ).fetchone()
            if row:
                if Source.model_validate_json(row[0]) != source:
                    raise DomainError(409, "registered source versions are immutable")
                return source
            if selectable:
                db.execute(
                    "UPDATE catalog_sources SET selectable=0 WHERE source_id=?", (source.source_id,)
                )
            db.execute(
                "INSERT INTO catalog_sources VALUES (?,?,?,?)",
                (source.source_id, source.version, int(selectable), source.model_dump_json()),
            )
        return source

    def manifest(self, corpus_id, db=None):
        if db is None:
            with self.repository.transaction() as connection:
                return self.manifest(corpus_id, connection)
        sources = tuple(
            Source.model_validate_json(row[0])
            for row in db.execute(
                "SELECT data FROM catalog_sources WHERE selectable=1 ORDER BY source_id"
            ).fetchall()
        )
        selected = tuple(s for s in sources if s.corpus_id == corpus_id)
        if not selected:
            raise DomainError(404, "selected provider corpus is unavailable")
        return selected

    def identify(self, artifact, db=None):
        if db is None:
            # A read may run inside a serialized mutation; do not acquire a second write lock.
            with sqlite3.connect(self.repository.path) as connection:
                return self.identify(artifact, connection)
        return next(
            (
                source
                for (data,) in db.execute("SELECT data FROM catalog_sources").fetchall()
                if (source := Source.model_validate_json(data)).artifact.sha256 == artifact.sha256
            ),
            None,
        )
