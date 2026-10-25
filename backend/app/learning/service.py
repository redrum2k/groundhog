"""Compose source-owner precedents; activate only qualified, controller-approved versions.

Uses existing immutable improvement records, activation pointers, catalog commands
and real run events. This adapter never accepts, funds, settles or reprices an order.
"""

import json
from hashlib import sha256
from pathlib import Path

from app.agents.source_knowledge import (
    InstitutionalMemory,
    ResolutionEvidence,
    SourceCase,
    SourceKnowledge,
    VendorExport,
)
from app.agents.source_preparation import compile_composed_sources
from app.contracts.catalog import RequestDraft, Source
from app.contracts.source_learning import (
    AttemptView,
    CandidateView,
    LearningEvent,
    LearningResult,
    LearningState,
    QualificationView,
    ReviewView,
)
from app.datasets import canonical, seed_registry, source_pin
from app.orders.service import DomainError
from app.storage.jobflow import digest

CUSTOMER = "AcmeFitness:controlled-local-demo"
OWNER = "simulated:DatumCo-local-source-owner"
CORPUS = "sf-aggregate-v1"
OPERATIONS = ("normalize_each_authorized_partition", "reject_overlap", "join_by_zip")


def implementation_digest():
    root = Path(__file__).resolve().parents[1]
    names = (
        "learning/service.py",
        "learning/qualification.py",
        "agents/source_knowledge.py",
        "agents/source_preparation.py",
        "catalog/preparation.py",
        "orders/catalog.py",
        "catalog/sources.py",
        "contracts/dataset.py",
        "contracts/source_learning.py",
        "datasets.py",
    )
    return digest({name: sha256((root / name).read_bytes()).hexdigest() for name in names})


class SourceLearning:
    def __init__(self, service, *, enabled=False):
        if not enabled or service.payments.mode != "mock":
            raise ValueError("source learning requires explicit controlled local mock mode")
        self.service = service
        self.memory = InstitutionalMemory(
            service.repository.path,
            CUSTOMER,
            "controlled-local",
            controlled_local=True,
        )
        self.grants = {OWNER: "DatumCo"}
        self.loaded_implementation = implementation_digest()
        self.shadow_memory = InstitutionalMemory(
            service.repository.path,
            CUSTOMER,
            "controlled-local-stateless-shadow",
            controlled_local=True,
        )

    def check_implementation(self):
        if implementation_digest() != self.loaded_implementation:
            raise DomainError(409, "application code changed; restart before learning operations")

    def engine(self, procedure_ids=()):
        self.check_implementation()
        return SourceKnowledge(
            self.service,
            self.memory,
            self.grants,
            controlled_local=True,
            procedure_ids=procedure_ids,
        )

    def _event(self, db, kind, text, actor, evidence_ids=(), request_id=None):
        record = self.memory.put(
            "source_learning_event",
            {
                "kind": kind,
                "text": text,
                "actor": actor,
                "evidence_ids": list(evidence_ids),
                "request_id": request_id,
                "created_at": self.service.clock().isoformat(),
            },
            db=db,
        )
        if request_id:
            self.service.effects.message(db, request_id, record["id"], text)
        return record

    def _replay(self, db, operation, command, actor):
        self.check_implementation()
        fingerprint = self.service.repository.fingerprint(operation + ":" + actor, command)
        replay = self.service.repository.replay(
            db,
            "learning:" + operation,
            command.idempotency_key,
            fingerprint,
            LearningResult,
        )
        return fingerprint, replay

    def _remember(self, db, operation, command, fingerprint, result):
        self.service.repository.remember(
            db,
            "learning:" + operation,
            command.idempotency_key,
            fingerprint,
            result,
        )
        return result

    def bundle(self, db=None):
        if db is None:
            with self.service.repository.transaction() as connection:
                return self.bundle(connection)
        row = db.execute(
            "SELECT data FROM catalog_records WHERE kind='learning_bundle' AND id=?",
            (CORPUS,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def active(self, db=None, *, require_current=True):
        self.check_implementation()
        if db is None:
            with self.service.repository.transaction() as connection:
                return self.active(connection, require_current=require_current)
        row = db.execute(
            "SELECT version_id FROM im_active WHERE customer_id=? AND product_id=?",
            (self.memory.customer_id, self.memory.product_id),
        ).fetchone()
        if not row:
            return None
        saved = db.execute(
            "SELECT body FROM im_records WHERE id=? AND kind='source_version'", (row[0],)
        ).fetchone()
        if not saved:
            raise DomainError(409, "active source version is missing")
        version = json.loads(saved[0])
        if require_current and version["implementation_sha256"] != implementation_digest():
            raise DomainError(409, "learning implementation changed; requalification required")
        return version

    def publish(self, command, actor):
        """Trusted source ingest, not a rule or final-answer injection endpoint."""
        seed_registry(self.service.registry, self.service.store)
        exports = [part.export for part in command.partitions]
        if any(raw.publisher != "DatumCo" or raw.scope != exports[0].scope for raw in exports):
            raise DomainError(422, "partitions must have the same authorized owner and scope")
        if (
            exports[0].scope.geography != "San Francisco"
            or exports[0].scope.category != "gym_or_fitness_app"
        ):
            raise DomainError(422, "controlled demo supports the existing SF gym/app product")
        if len({raw.source_family for raw in exports}) != len(exports):
            raise DomainError(422, "independently evidenced source families are required")
        if len({row.zip for raw in exports for row in raw.rows}) != sum(
            len(r.rows) for r in exports
        ):
            raise DomainError(422, "source partitions must be disjoint")
        coverage_source = next(
            s for s in self.service.registry.manifest(CORPUS) if s.source_id.endswith(":coverage")
        )
        coverage = json.loads(self.service.store.read(coverage_source.artifact))
        if {row.zip for raw in exports for row in raw.rows} != {
            row["zip"] for row in coverage["rows"]
        }:
            raise DomainError(
                422, "partitions must exactly cover the independently registered ZIPs"
            )
        with self.service.repository.transaction() as db:
            fingerprint, replay = self._replay(db, "publish", command, actor)
            if replay:
                return replay
            parts = []
            for part in command.partitions:
                raw, head = part.export, part.authority
                if (
                    head.publisher,
                    head.source_id,
                    head.source_version,
                    head.schema_hash,
                    head.scope,
                ) != (
                    raw.publisher,
                    raw.source_family,
                    raw.schema_version,
                    raw.schema_hash,
                    raw.scope,
                ) or not raw.source_id.startswith(CORPUS + ":learning:"):
                    raise DomainError(422, "source/authority identity or schema mismatch")
                artifact = self.service.store.put(
                    canonical(raw.model_dump(mode="json")), "application/json"
                )
                authority_artifact = self.service.store.put(
                    canonical(head.model_dump(mode="json")), "application/json"
                )
                authority_id = CORPUS + ":learning-authority:" + raw.source_family
                prior = [
                    Source.model_validate_json(r[0])
                    for r in db.execute(
                        "SELECT data FROM catalog_sources WHERE source_id=? ORDER BY version",
                        (authority_id,),
                    )
                ]
                same = next((s for s in prior if s.artifact == authority_artifact), None)
                metadata = dict(
                    corpus_id=CORPUS,
                    supplier_id=raw.publisher,
                    edition=raw.edition,
                    effective_date="2026-10-24",
                    authority="authorized_representative",
                    authority_record="Simulated DatumCo owner authority; controlled local demo.",
                )
                source = Source(
                    source_id=raw.source_id, version=raw.version, artifact=artifact, **metadata
                )
                authority = same or Source(
                    source_id=authority_id,
                    version=max((s.version for s in prior), default=0) + 1,
                    artifact=authority_artifact,
                    **metadata,
                )
                for item in (source, authority):
                    self.service.registry.register(item, db=db)
                parts.append(
                    {
                        "source": source.model_dump(mode="json"),
                        "authority": authority.model_dump(mode="json"),
                    }
                )
            record = self.memory.put(
                "source_bundle", {"partitions": parts, "origin": command.origin}, db=db
            )
            db.execute(
                "INSERT INTO catalog_records VALUES('learning_bundle',?,?) "
                "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
                (CORPUS, json.dumps(record)),
            )
            self._event(
                db,
                "source_received",
                "New synthetic source bytes received; no rule activated.",
                actor,
                (record["id"],),
            )
            return self._remember(
                db,
                "publish",
                command,
                fingerprint,
                LearningResult(status="RECEIVED", record_id=record["id"]),
            )

    def cases(self, request_id, bundle):
        cases = []
        for part in bundle["partitions"]:
            source, authority = (
                Source.model_validate(part["source"]),
                Source.model_validate(part["authority"]),
            )
            raw = VendorExport.model_validate_json(self.service.store.read(source.artifact))
            cases.append(
                SourceCase(
                    case_id=request_id + ":" + raw.source_family,
                    request_id=request_id,
                    customer_id=CUSTOMER,
                    source=source,
                    authority=authority,
                    scope=raw.scope,
                    requested_zips=tuple(row.zip for row in raw.rows),
                )
            )
        return cases

    def compile(self, request_id, command):
        fingerprint = self.service.repository.fingerprint("compile", command)
        with self.service.repository.transaction() as db:
            replay = self.service.repository.replay(
                db,
                f"request:{request_id}",
                command.idempotency_key,
                fingerprint,
                RequestDraft,
            )
            if replay:
                return replay
            draft = self.service.repository.load(db, "request", request_id, RequestDraft)
            bundle = self.bundle(db) if draft.corpus_id == CORPUS else None
            if (
                not bundle
                or db.execute(
                    "SELECT 1 FROM catalog_records WHERE kind='prepared_sources' AND id=?",
                    (request_id,),
                ).fetchone()
            ):
                return None
            if draft.status != "compiling" or draft.revision != command.expected_revision:
                return None
            configured = self.active(db, require_current=False)
            version = (
                configured
                if configured and configured["implementation_sha256"] == self.loaded_implementation
                else None
            )
        allowed = list(version["component_ids"]) if version else []
        # An owner's answer can resolve its own intake before global activation.
        # It grants no reuse on another request until the controller activates it.
        for procedure in self.memory.records("source_procedure"):
            resolution = self.memory.get("source_resolution", procedure["resolution_id"])
            witness = self.memory.get("source_encounter", resolution["encounter_id"])
            if witness["case"]["request_id"] == request_id:
                allowed.append(procedure["id"])
        engine = self.engine(allowed)
        cases = self.cases(request_id, bundle)
        results = [engine.assess(case) for case in cases]
        shadow_results = None
        if version:
            baseline = SourceKnowledge(
                self.service,
                self.shadow_memory,
                self.grants,
                controlled_local=True,
                procedure_ids=(),
            )
            shadow_results = [baseline.assess(case) for case in cases]
            if any(
                a["binding"] != b["binding"] for a, b in zip(results, shadow_results, strict=True)
            ):
                raise DomainError(409, "source changed during paired assessment")
        waiting = any(r["internal_reviews"] for r in results)
        reused_version = (
            version
            if version
            and not waiting
            and all(r["procedure_id"] in version["component_ids"] for r in results)
            else None
        )
        # Partial reuse still depends on approval. Keep the consent/revocation
        # guard even when we cannot attribute the whole bundle to this version.
        dependent_version = (
            version
            if version and any(r["procedure_id"] in version["component_ids"] for r in results)
            else None
        )
        with self.service.repository.transaction() as db:
            current = self.service.repository.load(db, "request", request_id, RequestDraft)
            if current.revision != draft.revision or current.status != "compiling":
                raise DomainError(409, "intake changed during source assessment")
            attempt = self.memory.put(
                "source_attempt",
                {
                    "request_id": request_id,
                    "bundle_id": bundle["id"],
                    "active_version": reused_version["id"] if reused_version else None,
                    "configured_version": configured["id"] if configured else None,
                    "encounter_ids": [r["encounter_id"] for r in results],
                    "internal_reviews": sum(r["internal_reviews"] for r in results),
                    "machine_operations": sum(len(r["tool_operations"]) for r in results),
                    "baseline_reviews": sum(r["internal_reviews"] for r in shadow_results)
                    if shadow_results is not None
                    else None,
                    "baseline_operations": sum(len(r["tool_operations"]) for r in shadow_results)
                    if shadow_results is not None
                    else None,
                    "source_hashes": [case.source.artifact.sha256 for case in cases],
                    "baseline_encounter_ids": [r["encounter_id"] for r in shadow_results]
                    if shadow_results is not None
                    else [],
                    "operation_basis": "source-assessment logical operations only",
                },
                db=db,
            )
            if waiting:
                current.status, current.error = "human_review", "Source-owner review required."
                current.revision += 1
                self.service.repository.put(db, "request", request_id, current)
                self._event(
                    db,
                    "human_needed",
                    "Human needed: source meaning is unresolved or authority blocks reuse.",
                    "employee",
                    attempt["encounter_ids"],
                    request_id,
                )
                self.service.effects.compiled(db, current)
                self.service.repository.remember(
                    db,
                    f"request:{request_id}",
                    command.idempotency_key,
                    fingerprint,
                    current,
                )
                return current
        result = compile_composed_sources(
            engine,
            tuple(r["encounter_id"] for r in results),
            idempotency_key=command.idempotency_key,
            learning_version=dependent_version["id"] if dependent_version else None,
            compile_fingerprint=fingerprint,
        )
        with self.service.repository.transaction() as db:
            self._event(
                db,
                "knowledge_reused" if reused_version else "source_prepared",
                "Approved procedure handled new source bytes without another internal review."
                if reused_version
                else "Owner resolutions composed; customer agreement still required.",
                "employee",
                (attempt["id"],),
                request_id,
            )
        return result

    def resolve(self, command, actor):
        if actor != OWNER:
            raise DomainError(403, "source-owner authority required")
        engine = self.engine()
        # Serialize source validation, evidence, derived procedure, intake resume,
        # event and command receipt as one mutation. A failed/rejected command
        # must not leave usable training knowledge behind.
        with self.service.repository.transaction() as db:
            fingerprint, replay = self._replay(db, "resolve", command, actor)
            if replay:
                return replay
            encounter = self.memory.get("source_encounter", command.encounter_id, db=db)
            case = SourceCase.model_validate(encounter["case"])
            raw, _ = engine.current(case, [], db=db)
            proof = ResolutionEvidence(
                actor_id=actor,
                origin="explicitly_simulated_provider_resolution",
                publisher=raw.publisher,
                source_family=raw.source_family,
                schema_version=raw.schema_version,
                source_pin=source_pin(case.source).model_dump(mode="json"),
                authority_pin=source_pin(case.authority).model_dump(mode="json"),
                schema_hash=raw.schema_hash,
                scope=case.scope,
                applicability=command.applicability,
                definition={"column": command.column, "unit": case.desired_unit},
                explanation=command.explanation,
            )
            artifact = self.service.store.put(
                canonical(proof.model_dump(mode="json")), "application/json"
            )
            resolution = engine.resolve(command.encounter_id, artifact, trusted_actor=actor, db=db)
            procedure = engine.induce(resolution["id"], db=db)
            draft = self.service.repository.load(db, "request", case.request_id, RequestDraft)
            if (
                draft.status not in ("compiling", "human_review")
                or self.service.clock() >= draft.deadline
            ):
                raise DomainError(409, "source resolution intake is no longer live")
            draft.status, draft.error = "compiling", None
            draft.revision += 1
            self.service.repository.put(db, "request", draft.request_id, draft)
            self._event(
                db,
                "human_resolved",
                f"Simulated source owner resolved {raw.source_family}: {command.column}.",
                actor,
                (resolution["id"], procedure["id"]),
                case.request_id,
            )
            return self._remember(
                db,
                "resolve",
                command,
                fingerprint,
                LearningResult(status="RESOLVED", record_id=procedure["id"]),
            )

    def propose(self, command, actor):
        # target_id is a bundle, not a mapping. All parameters come from evidence.
        bundle = self.memory.get("source_bundle", command.target_id)
        components = []
        for case_part in bundle["partitions"]:
            source = Source.model_validate(case_part["source"])
            raw = VendorExport.model_validate_json(self.service.store.read(source.artifact))
            found = [
                p
                for p in self.memory.records("source_procedure")
                if p["binding"]["source_family"] == raw.source_family
                and p["binding"]["authority"]
                == source_pin(Source.model_validate(case_part["authority"])).model_dump(mode="json")
            ]
            if not found or len({p["column"] for p in found}) != 1:
                raise DomainError(
                    409, "each component needs unconflicted independent owner evidence"
                )
            components.append(found[-1]["id"])
        if len(set(components)) < 2:
            raise DomainError(409, "two independently evidenced precedents are required")
        with self.service.repository.transaction() as db:
            fingerprint, replay = self._replay(db, "propose", command, actor)
            if replay:
                return replay
            active = self.active(db, require_current=False)
            candidate = self.memory.put(
                "source_candidate",
                {
                    "component_ids": components,
                    "operations": OPERATIONS,
                    "bundle_id": bundle["id"],
                    "baseline_version": active["id"] if active else None,
                    "implementation_sha256": implementation_digest(),
                },
                db=db,
            )
            db.execute("INSERT OR IGNORE INTO im_state VALUES(?, 'CANDIDATE')", (candidate["id"],))
            self._event(
                db,
                "knowledge_learned",
                "Learned a composed procedure from independent owner corrections; not active yet.",
                "employee",
                (candidate["id"], *components),
            )
            return self._remember(
                db,
                "propose",
                command,
                fingerprint,
                LearningResult(status="CANDIDATE", record_id=candidate["id"]),
            )

    def qualify(self, command, actor):
        from app.learning.qualification import qualify

        with self.service.repository.transaction() as db:
            fingerprint, replay = self._replay(db, "qualify", command, actor)
            if replay:
                return replay
        candidate = self.memory.get("source_candidate", command.target_id)
        if candidate["implementation_sha256"] != implementation_digest():
            raise DomainError(409, "candidate implementation changed")
        report = qualify(self, candidate)
        with self.service.repository.transaction() as db:
            _, replay = self._replay(db, "qualify", command, actor)
            if replay:
                return replay
            record = self.memory.put("source_qualification", report, db=db)
            db.execute(
                "UPDATE im_state SET status=? WHERE id=?",
                ("QUALIFIED" if report["passed"] else "REJECTED", candidate["id"]),
            )
            self._event(
                db,
                "procedure_qualified",
                f"Fresh qualification: {report['baseline_reviews']} -> "
                f"{report['candidate_reviews']} internal reviews; passed={report['passed']}.",
                actor,
                (record["id"], candidate["id"]),
            )
            return self._remember(
                db,
                "qualify",
                command,
                fingerprint,
                LearningResult(
                    status="QUALIFIED" if report["passed"] else "REJECTED", record_id=record["id"]
                ),
            )

    def transition(self, command, actor, operation):
        with self.service.repository.transaction() as db:
            fingerprint, replay = self._replay(db, operation, command, actor)
            if replay:
                return replay
            if operation == "approve":
                candidate = self.memory.get("source_candidate", command.target_id)
                reports = [
                    r
                    for r in self.memory.records("source_qualification")
                    if r["candidate_id"] == candidate["id"]
                ]
                active = self.active(db, require_current=False)
                if (
                    not reports
                    or not reports[-1]["passed"]
                    or candidate["baseline_version"] != (active["id"] if active else None)
                ):
                    raise DomainError(409, "passing qualification and unchanged baseline required")
                if reports[-1]["implementation_sha256"] != implementation_digest():
                    raise DomainError(409, "qualification implementation changed")
                version = self.memory.put(
                    "source_version",
                    {
                        "candidate_id": candidate["id"],
                        "component_ids": candidate["component_ids"],
                        "operations": candidate["operations"],
                        "qualification_id": reports[-1]["id"],
                        "approved_by": actor,
                        "approved_at": self.service.clock().isoformat(),
                        "implementation_sha256": implementation_digest(),
                        "previous_version": candidate["baseline_version"],
                    },
                    db=db,
                )
                db.execute("INSERT INTO im_state VALUES(?, 'APPROVED')", (version["id"],))
                db.execute("UPDATE im_state SET status='APPROVED' WHERE id=?", (candidate["id"],))
                self._event(
                    db,
                    "procedure_approved",
                    "Controller approved the qualified composed procedure; activation is explicit.",
                    actor,
                    (version["id"],),
                )
                result = LearningResult(status="APPROVED", record_id=version["id"])
            else:
                version = self.memory.get("source_version", command.target_id)
                state = db.execute(
                    "SELECT status FROM im_state WHERE id=?", (version["id"],)
                ).fetchone()[0]
                active = self.active(db, require_current=False)
                if operation == "activate":
                    if (
                        state != "APPROVED"
                        or version["previous_version"] != (active["id"] if active else None)
                        or version["implementation_sha256"] != implementation_digest()
                    ):
                        raise DomainError(409, "approved current version required")
                    db.execute(
                        "INSERT INTO im_active VALUES(?,?,?) ON CONFLICT(customer_id,product_id) "
                        "DO UPDATE SET version_id=excluded.version_id",
                        (self.memory.customer_id, self.memory.product_id, version["id"]),
                    )
                    if active:
                        db.execute(
                            "UPDATE im_state SET status='SUPERSEDED' WHERE id=?", (active["id"],)
                        )
                    status = "ACTIVE"
                elif operation == "revoke" and active and active["id"] == version["id"]:
                    db.execute(
                        "DELETE FROM im_active WHERE customer_id=? AND product_id=?",
                        (self.memory.customer_id, self.memory.product_id),
                    )
                    status = "REVOKED"
                else:
                    raise DomainError(409, "only the active version can be revoked")
                db.execute("UPDATE im_state SET status=? WHERE id=?", (status, version["id"]))
                self._event(
                    db,
                    "procedure_" + status.lower(),
                    f"Local learning version {status.lower()}; financial authority unchanged.",
                    actor,
                    (version["id"],),
                )
                result = LearningResult(status=status, record_id=version["id"])
            return self._remember(db, operation, command, fingerprint, result)

    def state(self):
        resolutions = self.memory.records("source_resolution")
        resolved = {r["encounter_id"] for r in resolutions}
        reviews = []
        for encounter in self.memory.records("source_encounter"):
            if encounter["result"]["internal_reviews"]:
                case = SourceCase.model_validate(encounter["case"])
                raw = VendorExport.model_validate_json(
                    self.service.store.read(case.source.artifact)
                )
                review_status = self.review_status(case, encounter, resolved)
                reviews.append(
                    ReviewView(
                        encounter_id=encounter["id"],
                        request_id=case.request_id,
                        source_family=raw.source_family,
                        source_sha256=case.source.artifact.sha256,
                        authority_sha256=case.authority.artifact.sha256,
                        columns=raw.columns,
                        reason=encounter["result"]["reason"],
                        resolved=encounter["id"] in resolved,
                        review_status=review_status,
                        actionable=review_status == "open",
                    )
                )
        with self.service.repository.transaction() as db:
            active = self.active(db, require_current=False)
            bundle = self.bundle(db)
            states = dict(db.execute("SELECT id,status FROM im_state"))
        reports = self.memory.records("source_qualification")
        fields = QualificationView.model_fields
        return LearningState(
            enabled=True,
            active_version=active["id"] if active else None,
            active_current=bool(
                active and active["implementation_sha256"] == self.loaded_implementation
            ),
            bundle_id=bundle["id"] if bundle else None,
            reviews=tuple(reviews),
            candidates=tuple(
                CandidateView(id=c["id"], component_ids=c["component_ids"], status=states[c["id"]])
                for c in self.memory.records("source_candidate")
            ),
            versions=tuple(
                CandidateView(id=v["id"], component_ids=v["component_ids"], status=states[v["id"]])
                for v in self.memory.records("source_version")
            ),
            attempts=tuple(
                AttemptView(**{k: a[k] for k in AttemptView.model_fields if k in a})
                for a in self.memory.records("source_attempt")
            ),
            events=tuple(
                LearningEvent(**{k: e[k] for k in LearningEvent.model_fields})
                for e in self.memory.records("source_learning_event")
            ),
            qualification=QualificationView(**{k: reports[-1][k] for k in fields})
            if reports
            else None,
        )

    def review_status(self, case, encounter, resolved):
        if encounter["id"] in resolved:
            return "resolved"
        with self.service.repository.transaction() as db:
            draft = self.service.repository.load(db, "request", case.request_id, RequestDraft)
            if self.service.clock() >= draft.deadline:
                return "expired"
            if draft.status not in ("compiling", "human_review"):
                return "closed"
            current = self.service.registry.manifest(draft.corpus_id, db)
            if case.source not in current or case.authority not in current:
                return "stale"
            from app.agents.source_knowledge import AuthorityHead

            head = AuthorityHead.model_validate_json(
                self.service.store.read(case.authority.artifact)
            )
            if self.service.clock() >= head.valid_until:
                return "expired"
            if (
                head.status != "active"
                or encounter["result"]["reason"] != "ambiguous_source_definition"
            ):
                return "blocked"
            if draft.status == "human_review" and draft.error != "Source-owner review required.":
                return "closed"
            return "open"
