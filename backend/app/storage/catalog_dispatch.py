"""Private compilation leases; catalog commands still own revisions and call budgets."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.contracts.catalog import RequestDraft


@dataclass(frozen=True)
class Compilation:
    token: str
    request_id: str
    revision: int
    attempt: int
    observed: bool = False


class CatalogDispatch:
    def __init__(self, repository):
        self.repository = repository
        with repository.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_compile_dispatch ("
                "token TEXT PRIMARY KEY, request_id TEXT NOT NULL, revision INTEGER NOT NULL, "
                "attempt INTEGER NOT NULL, lease_until REAL NOT NULL, outcome TEXT NOT NULL)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS catalog_compile_dispatch_request "
                "ON catalog_compile_dispatch(request_id, revision)"
            )

    def claim(self, now):
        with self.repository.transaction() as db:
            rows = db.execute(
                "SELECT data FROM catalog_records WHERE kind='request' "
                "AND json_extract(data, '$.status')='compiling' ORDER BY rowid"
            ).fetchall()
            for row in rows:
                draft = RequestDraft.model_validate_json(row[0])
                # The fourth call may still be in flight. The existing service's
                # budget-exhaustion branch does not advance its result revision.
                # Do not invoke that branch and race a late result: wait for the
                # original deadline, whose service gate invalidates the reservation.
                if draft.compiler_calls >= 4 and now < draft.deadline:
                    continue
                if db.execute(
                    "SELECT 1 FROM catalog_compile_dispatch WHERE request_id=? "
                    "AND outcome IN ('running','uncertain') AND lease_until>?",
                    (draft.request_id, now.timestamp()),
                ).fetchone():
                    continue

                # The internal compile endpoint predates this scheduler. An unfinished
                # command response is a *spent* call reservation, never a completed result.
                # Give an unowned call a lease on first observation before superseding it.
                unowned = db.execute(
                    "SELECT 1 FROM catalog_commands WHERE scope=? "
                    "AND json_extract(fingerprint, '$.operation')='compile' "
                    "AND json_extract(response, '$.status')='compiling' "
                    "AND json_extract(response, '$.revision')=? "
                    "AND NOT EXISTS (SELECT 1 FROM catalog_compile_dispatch "
                    "WHERE request_id=? AND revision=?) LIMIT 1",
                    (
                        f"request:{draft.request_id}",
                        draft.revision,
                        draft.request_id,
                        draft.revision - 1,
                    ),
                ).fetchone()
                observed = bool(unowned) and now < draft.deadline
                claim = Compilation(
                    token=f"dispatch-{uuid4().hex}",
                    request_id=draft.request_id,
                    revision=draft.revision - int(observed),
                    attempt=draft.compiler_calls + int(not observed),
                    observed=observed,
                )
                # Expired reservations remain uncertain history. Recovery uses a fresh
                # command at the current revision; it never replays a partial response
                # as success or restores the consumed compiler budget.
                db.execute(
                    "UPDATE catalog_compile_dispatch SET outcome='uncertain' "
                    "WHERE request_id=? AND outcome='running'",
                    (draft.request_id,),
                )
                db.execute(
                    "INSERT INTO catalog_compile_dispatch VALUES (?,?,?,?,?,?)",
                    (
                        claim.token,
                        claim.request_id,
                        claim.revision,
                        claim.attempt,
                        (now + timedelta(seconds=45)).timestamp(),
                        "uncertain" if observed else "running",
                    ),
                )
                return claim
        return None

    def finish(self, claim, outcome):
        with self.repository.transaction() as db:
            db.execute(
                "UPDATE catalog_compile_dispatch SET outcome=? WHERE token=? AND outcome='running'",
                (outcome, claim.token),
            )
