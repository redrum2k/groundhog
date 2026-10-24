"""Bounded selection only: CatalogService owns execution and result application gates."""

import logging
from time import monotonic

from app.contracts.catalog import CatalogOrder, RevisionCommand
from app.orders.service import DomainError
from app.runtime.catalog_policy import authorization_ready
from app.storage.catalog_dispatch import CatalogDispatch

logger = logging.getLogger(__name__)


class CatalogWorker:
    def __init__(self, service):
        self.service = service
        self.dispatch = CatalogDispatch(service.repository)
        self._prefer_compile = True
        self._order_cursor = ""

    def run_once(self) -> bool:
        """Run one compilation/job attempt, observe an interrupted call, or return idle.

        Exceptions are redacted and isolated here. Crashes retain durable reservations;
        subsequent consumers recover only after expiry, through the service's gates.
        """
        stages = (self._compile, self._work)
        if not self._prefer_compile:
            stages = stages[::-1]
        self._prefer_compile = not self._prefer_compile
        return any(stage() for stage in stages)

    def _compile(self):
        claim = self.dispatch.claim(self.service.clock())
        if claim is None:
            return False
        started = monotonic()
        outcome = "uncertain"
        try:
            if not claim.observed:
                result = self.service.compile_request(
                    claim.request_id,
                    RevisionCommand(expected_revision=claim.revision, idempotency_key=claim.token),
                )
                outcome = result.status if result.status != "compiling" else "uncertain"
        except DomainError as exc:
            outcome = "stale" if exc.status == 409 else "uncertain"
        except Exception:
            # No exception strings: transport errors can contain documents or credentials.
            # A reservation may already have committed; retain its lease and spent call.
            pass
        finally:
            self.dispatch.finish(claim, outcome)
            logger.info(
                "catalog stage=compile request_id=%s dispatch_id=%s attempt=%s "
                "elapsed_ms=%s outcome=%s",
                claim.request_id,
                claim.token,
                claim.attempt,
                int((monotonic() - started) * 1000),
                outcome,
            )
        return True

    def _work(self):
        now = self.service.clock()
        with self.service.repository.transaction() as db:
            orders = self.service.repository.all(db, "order", CatalogOrder)
        # Rotate within this consumer so a raced/failed claim cannot starve another order.
        orders.sort(key=lambda o: (o.snapshot.order_id <= self._order_cursor, o.snapshot.order_id))
        for order in orders:
            if (
                order.schema_version < 4
                or order.order_state
                in (
                    "awaiting_authorization",
                    "human_review",
                    "closed",
                    "pending_approval",
                    "waiting_evidence",
                    "operational_failure",
                )
                or not authorization_ready(order.authorization)
                or now >= order.authorization.expires_at
            ):
                continue
            job = next(
                (
                    j
                    for j in order.jobs
                    if j.binding == order.binding
                    and (
                        j.status == "queued"
                        or j.status == "running"
                        and j.lease_until is not None
                        and j.lease_until <= now
                    )
                ),
                None,
            )
            if job is None:
                continue
            order_id = order.snapshot.order_id
            self._order_cursor = order_id
            started = monotonic()
            outcome = "uncertain"
            try:
                # Claim, attempt accounting, deadlines and binding checks are atomic in
                # the service. Selection is advisory and grants no execution authority.
                result = self.service.run_one(order_id)
                outcome = result.order_state
            except DomainError as exc:
                outcome = "stale" if exc.status == 409 else "uncertain"
            except Exception:
                pass
            logger.info(
                "catalog stage=%s order_id=%s job_id=%s attempt=%s elapsed_ms=%s outcome=%s",
                job.kind,
                order_id,
                job.job_id,
                job.attempts + 1,
                int((monotonic() - started) * 1000),
                outcome,
            )
            return True
        return False
