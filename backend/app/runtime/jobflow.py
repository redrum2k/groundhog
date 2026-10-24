"""Authenticated mutation boundary. Workers consume persisted intents separately."""

import base64
import binascii
import hashlib
import json
import os
import secrets
from datetime import timedelta

from app.contracts.jobflow import Actor, OrderView
from app.orders.jobflow import create_order, prepare_intake
from app.payments.jobflow import project
from app.provider.jobflow import store_evidence
from app.runtime.jobflow_policy import invalidate, refresh_quotes, require, utcnow
from app.storage.jobflow import DomainError, Store

DEMO_ACTORS = [
    Actor(id="customer", name="Northwind buyer", role="customer", customer_id="northwind"),
    Actor(id="customer_other", name="Other buyer", role="customer", customer_id="other"),
    *[
        Actor(id=role, name=f"Demo {role}", role=role)
        for role in ("provider", "investigator", "controller", "executor")
    ],
]


def model_configured():
    try:
        return bool(
            os.environ.get("ANTHROPIC_API_KEY")
            and os.environ.get("ANTHROPIC_MODEL")
            and int(os.environ.get("JOBFLOW_ANTHROPIC_MAX_CALLS", "0")) > 0
        )
    except ValueError:
        return False


class Jobflow:
    def __init__(
        self,
        path,
        *,
        demo=False,
        clock=utcnow,
        investigator=None,
        document_extractor=None,
        authenticator=None,
    ):
        self.store = Store(path)
        self.demo = demo
        self.clock = clock
        self.investigator = investigator
        self.document_extractor = document_extractor
        self.authenticator = authenticator
        if demo:
            with self.store.connect(write=True) as db:
                for actor in DEMO_ACTORS:
                    db.execute(
                        "INSERT OR IGNORE INTO jf_actors VALUES(?,?)",
                        (actor.id, actor.model_dump_json()),
                    )

    def actors(self):
        if not self.demo:
            raise DomainError("Local demo identities are disabled", 404)
        return DEMO_ACTORS

    def session(self, actor_id):
        if not self.demo:
            raise DomainError("Local demo sessions are disabled", 404)
        with self.store.connect(write=True) as db:
            row = db.execute("SELECT body FROM jf_actors WHERE id=?", (actor_id,)).fetchone()
            if not row:
                raise DomainError("Unknown registered actor", 403)
            actor = Actor.model_validate_json(row[0])
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO jf_sessions VALUES(?,?,?)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    actor.id,
                    (self.clock() + timedelta(hours=12)).isoformat(),
                ),
            )
        return {"token": token, "actor": actor.model_dump(mode="json")}

    def authenticate(self, token):
        if self.authenticator:
            actor = self.authenticator(token)
            if actor is not None:
                return Actor.model_validate(actor)
        if token and self.demo:
            with self.store.connect() as db:
                row = db.execute(
                    """SELECT a.body FROM jf_sessions s JOIN jf_actors a
                    ON a.id=s.actor_id WHERE s.token_hash=? AND s.expires_at>?""",
                    (
                        hashlib.sha256(token.encode()).hexdigest(),
                        self.clock().isoformat(),
                    ),
                ).fetchone()
                if row:
                    return Actor.model_validate_json(row[0])
        raise DomainError("Authenticated server-side session required", 401)

    def available(self, db):
        if not model_configured():
            return False
        used = db.execute("SELECT count(*) FROM jf_model_calls").fetchone()[0]
        return used < int(os.environ["JOBFLOW_ANTHROPIC_MAX_CALLS"])

    def view(self, actor, order_id):
        with self.store.connect() as db:
            order = self.store.get(db, order_id)
            require(actor, order)
            project(db, order, self.clock())
            order.model_available = self.available(db)
            return order

    def orders(self, actor):
        with self.store.connect() as db:
            orders = [
                OrderView.model_validate_json(row[0])
                for row in db.execute("SELECT body FROM jf_orders ORDER BY rowid DESC")
            ]
            result = []
            for order in orders:
                if actor.role != "customer" or actor.customer_id == order.customer_id:
                    project(db, order, self.clock())
                    order.model_available = self.available(db)
                    result.append(order)
            return result

    def events(self, actor, order_id, after=0):
        with self.store.connect() as db:
            require(actor, self.store.get(db, order_id))
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM jf_events WHERE order_id=? AND sequence>? ORDER BY sequence",
                    (order_id, after),
                )
            ]

    def artifact(self, actor, order_id, source_id):
        with self.store.connect() as db:
            require(actor, self.store.get(db, order_id))
            return self.store.artifact(db, order_id, source_id)

    def create(self, actor, request):
        require(actor, roles={"customer", "provider"})
        envelope = {"route": "create", "body": request.model_dump(mode="json")}
        with self.store.connect() as db:
            prior = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if prior is not None:
                return OrderView.model_validate(prior)
        records = prepare_intake(request)
        with self.store.connect(write=True) as db:
            prior = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if prior is not None:
                return OrderView.model_validate(prior)
            order = create_order(
                db, self.store, actor, request, records, self.clock(), self.available(db)
            )
            self.store.save(db, order)
            self.store.receipt(
                db, actor.id, request.idempotency_key, envelope, order.model_dump(mode="json")
            )
            return order

    def mutate(self, actor, order_id, request, route, roles, transform):
        envelope = {"route": route, "order_id": order_id, "body": request.model_dump(mode="json")}
        with self.store.connect(write=True) as db:
            order = self.store.get(db, order_id)
            require(actor, order, roles)
            prior = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if prior is not None:
                return prior
            if order.revision != request.expected_revision:
                raise DomainError("Expected revision is stale")
            now = self.clock()
            order.revision += 1

            def emit(kind, **payload):
                self.store.event(db, order, actor.id, request.idempotency_key, now, kind, **payload)

            response = transform(db, order, now, emit)
            refresh_quotes(order, now, emit)
            project(db, order, now)
            order.model_available = self.available(db)
            self.store.save(db, order)
            if response is None:
                response = order.model_dump(mode="json")
            self.store.receipt(db, actor.id, request.idempotency_key, envelope, response)
            return response

    def command(self, actor, order_id, command):
        from app.runtime.jobflow_commands import ROLES, apply_command

        return OrderView.model_validate(
            self.mutate(
                actor,
                order_id,
                command,
                "command",
                ROLES[command.verb],
                lambda db, order, now, emit: apply_command(
                    self, db, order, actor, command, now, emit
                ),
            )
        )

    def upload(self, actor, order_id, request):
        require(actor, self.view(actor, order_id), {"customer", "provider", "investigator"})
        # Check replay before invoking parsers, so a previously accepted request is stable.
        envelope = {
            "route": "upload",
            "order_id": order_id,
            "body": request.model_dump(mode="json"),
        }
        with self.store.connect() as db:
            prior = self.store.replay(db, actor.id, request.idempotency_key, envelope)
            if prior is not None:
                return OrderView.model_validate(prior)
        if len(request.content_base64) > 8_000_000:
            raise DomainError("Upload exceeds six megabytes", 413)
        try:
            raw = base64.b64decode(request.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise DomainError("Invalid base64 upload", 422) from exc
        if not raw:
            raise DomainError("Empty upload", 422)
        extractor = self.document_extractor
        if extractor is None:
            try:
                from app.investigation.documents import extract_document
            except ImportError as exc:
                raise DomainError("Document extraction integration is unavailable", 503) from exc
            extractor = extract_document
        try:
            parsed = extractor(raw, request.filename, request.media_type)
        except (ValueError, RuntimeError) as exc:
            raise DomainError("Document could not be safely extracted", 422) from exc
        if parsed.get("sha256", hashlib.sha256(raw).hexdigest()) != hashlib.sha256(raw).hexdigest():
            raise DomainError("Extractor digest does not match uploaded bytes", 422)

        def apply(db, order, now, emit):
            from app.runtime.jobflow_policy import find

            if request.issue_id:
                issue = find(order.issues, request.issue_id, "Issue")
                issue.owner = "investigator"
                issue.next_action = "Investigate newly supplied party evidence"
            version = 1 + max(
                (item.version for item in order.evidence if item.filename == request.filename),
                default=0,
            )
            evidence = store_evidence(
                db,
                order,
                raw,
                filename=request.filename,
                media_type=request.media_type,
                kind=request.kind,
                authority="PARTY_ASSERTION",
                actor_id=actor.id,
                now=now,
                extraction=parsed,
                version=version,
            )
            invalidate(order, now)
            emit("evidence.collected", source_id=evidence.id, issue_id=request.issue_id)

        return OrderView.model_validate(
            self.mutate(
                actor,
                order_id,
                request,
                "upload",
                {"customer", "provider", "investigator"},
                apply,
            )
        )

    def investigate(self, actor, order_id, request):
        from app.runtime.jobflow_investigations import queue_investigation

        return self.mutate(
            actor,
            order_id,
            request,
            "investigate",
            {"investigator"},
            lambda db, order, now, emit: queue_investigation(
                self,
                db,
                order,
                request.issue_id,
                request.mode,
                now,
                emit,
            ),
        )
