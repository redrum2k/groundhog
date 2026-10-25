"""Sandbox-only institutional knowledge from an authorized operational resolution.

No field-name heuristics, imported corpora, model calls or settlement actions.
Both agents inspect the same current source/authority; an empty experience scope
is the stateless control. Only a resolved observed exception can yield a procedure.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from app.contracts.catalog import Artifact, RequestDraft, Source
from app.contracts.data_product import Frozen
from app.contracts.dataset import DatasetRow, DatasetSource
from app.datasets import source_pin
from app.storage import improvement
from app.storage.jobflow import Store, digest

UNIT = "unique_adults_per_zip"
PRODUCT = "institutional-source-knowledge-v1"


class SourceScope(Frozen):
    geography: Literal["San Francisco", "Oakland"]
    age_min: Literal[25] = 25
    age_max: Literal[34] = 34
    category: Literal["gym_or_fitness_app", "gym_app_or_yoga"] = "gym_or_fitness_app"
    population: Literal["synthetic_adults"] = "synthetic_adults"
    groups_disjoint: Literal[True] = True


class VendorRow(Frozen):
    zip: str = Field(pattern=r"^\d{5}$")
    area: str = Field(min_length=1, max_length=80)
    values: dict[str, StrictInt | None]
    status: Literal["released", "suppressed", "unknown"]


class VendorExport(Frozen):
    source_id: str
    source_family: str
    schema_version: StrictInt = Field(ge=1)
    version: StrictInt = Field(ge=1)
    publisher: str
    edition: str
    scope: SourceScope
    columns: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)]
    rows: Annotated[tuple[VendorRow, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def validate_schema(self):
        import re

        if len(set(self.columns)) != len(self.columns) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]{0,30}", c) for c in self.columns
        ):
            raise ValueError("unique safe column identifiers required")
        if len({r.zip for r in self.rows}) != len(self.rows):
            raise ValueError("duplicate source keys")
        for row in self.rows:
            if set(row.values) != set(self.columns):
                raise ValueError("row differs from declared schema")
            if row.status != "released" and any(v is not None for v in row.values.values()):
                raise ValueError("non-released raw values must already be redacted")
            if row.status == "released" and any(v is None or v < 50 for v in row.values.values()):
                raise ValueError("released aggregate values must be integers at least 50")
        return self

    @property
    def schema_hash(self):
        return digest({"columns": self.columns, "value_type": "nullable_integer", "key": "zip"})


class Definition(Frozen):
    column: str
    unit: str


class AuthorityHead(Frozen):
    publisher: str
    source_id: str
    source_version: StrictInt
    schema_hash: str
    epoch: str
    scope: SourceScope
    status: Literal["active", "revoked", "conflict"] = "active"
    valid_until: AwareDatetime
    definitions: tuple[Definition, ...] = ()


class SourceCase(Frozen):
    case_id: str = Field(min_length=1, max_length=120)
    request_id: str
    customer_id: str
    source: Source
    authority: Source
    scope: SourceScope
    desired_unit: Literal["unique_adults_per_zip"] = UNIT
    requested_zips: Annotated[tuple[str, ...], Field(min_length=1, max_length=100)]


class ResolutionEvidence(Frozen):
    origin: Literal["explicitly_simulated_provider_resolution"]
    actor_id: str
    publisher: str
    source_family: str
    schema_version: StrictInt
    source_pin: dict
    authority_pin: dict
    schema_hash: str
    scope: SourceScope
    applicability: Literal["source_edition", "this_order_only"]
    definition: Definition
    explanation: str = Field(min_length=1, max_length=1000)


def cite(artifact, pointer, value, role):
    return {
        "artifact": artifact.model_dump(mode="json"),
        "pointer": pointer,
        "value": value,
        "role": role,
    }


def binding(case, raw):
    return {
        "source": source_pin(case.source).model_dump(mode="json"),
        "authority": source_pin(case.authority).model_dump(mode="json"),
        "publisher": raw.publisher,
        "source_family": raw.source_family,
        "schema_version": raw.schema_version,
        "edition": raw.edition,
        "schema_hash": raw.schema_hash,
        "scope": case.scope.model_dump(mode="json"),
        "unit": case.desired_unit,
    }


def procedure_scope(bound):
    # The authority explicitly covers the source-family schema edition, not the
    # old row values. Exact batch hashes remain in each encounter and citation.
    return {k: v for k, v in bound.items() if k != "source"}


class InstitutionalMemory:
    """An immutable experience book in the application's existing SQLite database."""

    def __init__(
        self, path, customer_id, experience_scope, *, sandbox=False, controlled_local=False
    ):
        if not sandbox and not controlled_local:
            raise ValueError("institutional learning is sandbox-only")
        self.controlled_local = controlled_local
        self.store = Store(path)
        self.customer_id = customer_id
        self.product_id = PRODUCT + ":" + experience_scope
        improvement.migrate(self.store)

    def records(self, kind, *, db=None):
        if db is None:
            with self.store.connect() as connection:
                return self.records(kind, db=connection)
        return improvement.records(db, kind, self.customer_id, self.product_id)

    def put(self, kind, body, *, db=None):
        if db is None:
            with self.store.connect(write=True) as connection:
                return self.put(kind, body, db=connection)
        body = {**body, "customer_id": self.customer_id, "product_id": self.product_id}
        identifier = "institutional-" + digest({"kind": kind, "body": body})
        body["id"] = identifier
        existing = db.execute("SELECT body FROM im_records WHERE id=?", (identifier,)).fetchone()
        if not existing:
            improvement.put(db, kind, body)
        return body

    def get(self, kind, identifier, *, db=None):
        result = next((r for r in self.records(kind, db=db) if r["id"] == identifier), None)
        if result is None:
            raise ValueError("experience unavailable in this customer/book scope")
        body = {k: v for k, v in result.items() if k != "id"}
        if identifier != "institutional-" + digest({"kind": kind, "body": body}):
            raise ValueError("experience content binding failed")
        return result


class SourceKnowledge:
    """Trusted local application adapter; not a new authentication or payment API."""

    def __init__(
        self,
        service,
        memory,
        authorized_resolvers,
        *,
        sandbox=False,
        controlled_local=False,
        procedure_ids=None,
    ):
        if (not sandbox and not controlled_local) or (
            memory.store.path.resolve() != service.repository.path.resolve()
        ):
            raise ValueError("sandbox and shared application database required")
        if controlled_local and not memory.controlled_local:
            raise ValueError("controlled local memory required")
        self.controlled_local = controlled_local
        # Live reuse is explicit and fail-closed; sandbox comparisons retain their
        # original all-procedures behavior. Never implicitly activate a new record.
        self.procedure_ids = frozenset(procedure_ids or ()) if controlled_local else procedure_ids
        self.service, self.memory = service, memory
        # Trusted server configuration, never taken from customer text or an evidence file.
        self.authorized_resolvers = dict(authorized_resolvers)  # actor -> publisher

    def current(self, case, operations, *, db=None):
        if db is None:
            with self.service.repository.transaction() as connection:
                return self.current(case, operations, db=connection)
        if case.customer_id != self.memory.customer_id:
            raise ValueError("customer scope mismatch")
        operations.append("load_current_request")
        draft = self.service.repository.load(db, "request", case.request_id, RequestDraft)
        resolving = (
            self.controlled_local
            and draft.status == "human_review"
            and draft.error == "Source-owner review required."
        )
        if (
            draft.status != "compiling" and not resolving
        ) or self.service.clock() >= draft.deadline:
            raise ValueError("source preparation needs a live, unaccepted intake")
        if case.source.corpus_id != draft.corpus_id or case.authority.corpus_id != draft.corpus_id:
            raise ValueError("source corpus differs from selected request")
        operations.append("read_current_registry")
        manifest = self.service.registry.manifest(draft.corpus_id, db)
        if case.source not in manifest or case.authority not in manifest:
            raise ValueError("source or authority pin is no longer current")
        if any(s.authority == "unverified" for s in (case.source, case.authority)):
            raise ValueError("unestablished source authority")
        operations.append("read_source_bytes")
        raw = VendorExport.model_validate_json(self.service.store.read(case.source.artifact))
        operations.append("read_authority_bytes")
        head = AuthorityHead.model_validate_json(self.service.store.read(case.authority.artifact))
        if (
            (raw.source_id, raw.version, raw.edition, raw.publisher)
            != (
                case.source.source_id,
                case.source.version,
                case.source.edition,
                case.source.supplier_id,
            )
            or (head.source_id, head.source_version, head.publisher, head.schema_hash)
            != (raw.source_family, raw.schema_version, raw.publisher, raw.schema_hash)
            or case.authority.supplier_id != raw.publisher
        ):
            raise ValueError("source identity, publisher or schema authority mismatch")
        if raw.scope != case.scope or head.scope != case.scope:
            raise ValueError("scope mismatch")
        if len(set(case.requested_zips)) != len(case.requested_zips) or not set(
            case.requested_zips
        ) <= {r.zip for r in raw.rows}:
            raise ValueError("requested ZIPs are outside the source scope")
        return raw, head

    def assess(self, case):
        case = SourceCase.model_validate(case)
        operations = []
        raw, head = self.current(case, operations)
        bound = binding(case, raw)
        result = {
            "status": "internal_review",
            "reason": "ambiguous_source_definition",
            "origin": "explicitly_simulated_runtime",
            "binding": bound,
            "procedure_id": None,
            "resolution_id": None,
            "column": None,
            "rows": [],
            "citations": [],
            "tool_operations": operations,
            "internal_reviews": 1,
            "customer_consent_required": True,
            "forbidden_actions": [],
            "normalized": None,
        }
        if head.status != "active" or self.service.clock() >= head.valid_until:
            result["reason"] = "authority_" + (
                head.status if head.status != "active" else "expired"
            )
            return self._record(case, result)
        operations.append("inspect_current_definitions")
        definitions = [
            (i, d) for i, d in enumerate(head.definitions) if d.unit == case.desired_unit
        ]
        if any(d.column not in raw.columns for _, d in definitions):
            result["reason"] = "invalid_current_definition"
            return self._record(case, result)
        if len({d.column for _, d in definitions}) > 1:
            result["reason"] = "conflicting_current_definitions"
            return self._record(case, result)
        operations.append("retrieve_previous_procedures")
        all_procedures = [
            p
            for p in self.memory.records("source_procedure")
            if p["binding"] == procedure_scope(bound)
        ]
        # Never select 'latest wins' when two authorized resolutions disagree.
        if len({p["column"] for p in all_procedures} | {d.column for _, d in definitions}) > 1:
            result["reason"] = "conflicting_retained_definition"
            return self._record(case, result)
        procedures = [
            p for p in all_procedures if self.procedure_ids is None or p["id"] in self.procedure_ids
        ]
        if definitions:
            index, definition = definitions[0]
            column = definition.column
            result["citations"].extend(
                [
                    cite(
                        case.authority.artifact,
                        f"/definitions/{index}/column",
                        column,
                        "definition",
                    ),
                    cite(
                        case.authority.artifact,
                        f"/definitions/{index}/unit",
                        case.desired_unit,
                        "unit",
                    ),
                ]
            )
            result["reason"] = "current_authoritative_definition"
        elif procedures:
            procedure = self.memory.get("source_procedure", procedures[0]["id"])
            operations.append("read_previous_resolution_evidence")
            resolution = self.memory.get("source_resolution", procedure["resolution_id"])
            proof_artifact = Artifact.model_validate(resolution["evidence"])
            proof = ResolutionEvidence.model_validate_json(self.service.store.read(proof_artifact))
            witness = self.memory.get("source_encounter", resolution["encounter_id"])
            previous_case = SourceCase.model_validate(witness["case"])
            operations.append("read_previous_witness_source")
            previous_raw = VendorExport.model_validate_json(
                self.service.store.read(previous_case.source.artifact)
            )
            self._validate_resolution(previous_case, previous_raw, proof, resolution["actor_id"])
            if procedure_scope(binding(previous_case, previous_raw)) != procedure["binding"]:
                raise ValueError("procedure scope exceeds its witnessed source resolution")
            if (
                proof.applicability != "source_edition"
                or procedure["column"] != proof.definition.column
            ):
                raise ValueError("procedure differs from source-scoped resolved evidence")
            if procedure["operations"] != [
                "check_source_and_authority_pins",
                "read_mapped_column",
                "validate_null_suppression",
                "emit_typed_source",
            ]:
                raise ValueError("procedure contains unapproved operations")
            column = proof.definition.column
            result.update(
                procedure_id=procedure["id"],
                resolution_id=resolution["id"],
                reason="retained_authoritative_resolution",
            )
            result["citations"].extend(
                [
                    cite(proof_artifact, "/definition/column", column, "definition"),
                    cite(proof_artifact, "/definition/unit", case.desired_unit, "unit"),
                ]
            )
        else:
            return self._record(case, result)
        operations.append("read_mapped_source_column")
        normalized = DatasetSource(
            source_id=case.source.corpus_id + ":" + case.scope.category,
            version=case.source.version,
            edition=raw.edition,
            **case.scope.model_dump(),
            count_unit=case.desired_unit,
            rows=tuple(
                DatasetRow(zip=r.zip, area=r.area, count=r.values[column], status=r.status)
                for r in raw.rows
            ),
        )
        # Returned query rows are freshly computed, never copied from the old exception.
        for index, row in enumerate(raw.rows):
            if row.zip in case.requested_zips:
                result["rows"].append(
                    {"zip": row.zip, "count": row.values[column], "status": row.status}
                )
                result["citations"].append(
                    cite(
                        case.source.artifact,
                        f"/rows/{index}/values/{column}",
                        row.values[column],
                        "value",
                    )
                )
        result["citations"].append(cite(case.authority.artifact, "/epoch", head.epoch, "authority"))
        operations.append("validate_typed_source")
        result.update(
            status="ready_for_customer_quote",
            internal_reviews=0,
            column=column,
            normalized=normalized.model_dump(mode="json"),
        )
        # Do not silently commit a decision against an authority that changed mid-read.
        current = self.service.registry.manifest(case.authority.corpus_id)
        if (
            case.authority not in current
            or case.source not in current
            or self.service.clock() >= head.valid_until
        ):
            raise ValueError("source or authority changed during preparation")
        return self._record(case, result)

    def _record(self, case, result):
        if result["internal_reviews"]:
            result["tool_operations"].append("request_internal_review")
        record = self.memory.put(
            "source_encounter",
            {
                "case": case.model_dump(mode="json"),
                "result": result,
                "origin": "explicitly_simulated_runtime",
            },
        )
        return {**result, "encounter_id": record["id"]}

    def _validate_resolution(self, case, raw, proof, actor_id):
        if self.authorized_resolvers.get(actor_id) != raw.publisher or proof.actor_id != actor_id:
            raise ValueError("resolver lacks source-owner authority")
        if (
            proof.publisher != raw.publisher
            or proof.source_family != raw.source_family
            or proof.schema_version != raw.schema_version
            or proof.source_pin != source_pin(case.source).model_dump(mode="json")
            or proof.authority_pin != source_pin(case.authority).model_dump(mode="json")
            or proof.schema_hash != raw.schema_hash
            or proof.scope != case.scope
            or proof.definition.unit != case.desired_unit
            or proof.definition.column not in raw.columns
        ):
            raise ValueError(
                "resolution does not establish this source, scope and semantic mapping"
            )

    def resolve(self, encounter_id, evidence, *, trusted_actor, db=None):
        if db is None:
            with self.service.repository.transaction() as connection:
                return self.resolve(
                    encounter_id, evidence, trusted_actor=trusted_actor, db=connection
                )
        encounter = self.memory.get("source_encounter", encounter_id, db=db)
        if encounter["result"]["reason"] != "ambiguous_source_definition":
            raise ValueError("only an observed unresolved source ambiguity can be resolved")
        case = SourceCase.model_validate(encounter["case"])
        raw, head = self.current(case, [], db=db)
        if head.status != "active" or self.service.clock() >= head.valid_until:
            raise ValueError("resolution authority is not currently valid")
        evidence = Artifact.model_validate(evidence)
        proof = ResolutionEvidence.model_validate_json(self.service.store.read(evidence))
        self._validate_resolution(case, raw, proof, trusted_actor)
        return self.memory.put(
            "source_resolution",
            {
                "encounter_id": encounter_id,
                "binding": binding(case, raw),
                "evidence": evidence.model_dump(mode="json"),
                "actor_id": trusted_actor,
                "column": proof.definition.column,
                "applicability": proof.applicability,
                "origin": proof.origin,
            },
            db=db,
        )

    def induce(self, resolution_id, *, db=None):
        resolution = self.memory.get("source_resolution", resolution_id, db=db)
        if resolution["applicability"] != "source_edition":
            raise ValueError("an order-specific answer cannot become a cross-order procedure")
        # Parameters are obtained exclusively from the authorized resolution, not
        # query text, field-name heuristics, fixtures, expected rows or final answers.
        return self.memory.put(
            "source_procedure",
            {
                "resolution_id": resolution_id,
                "binding": procedure_scope(resolution["binding"]),
                "column": resolution["column"],
                "unit": resolution["binding"]["unit"],
                "operations": [
                    "check_source_and_authority_pins",
                    "read_mapped_column",
                    "validate_null_suppression",
                    "emit_typed_source",
                ],
                "origin": resolution["origin"],
                "version": 1,
                "activation": "approval_required" if self.controlled_local else "sandbox_only",
            },
            db=db,
        )
