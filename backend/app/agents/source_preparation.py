"""Sandbox bridge to ordinary compilation with draft-local source/evidence pins.

No shared registry publication, accepted snapshot mutation or implicit consent.
"""

from app.agents.source_knowledge import AuthorityHead, SourceCase
from app.catalog.preparation import PreparedSources, preparation_fingerprint
from app.contracts.catalog import Artifact, RequestDraft, RevisionCommand, Source
from app.contracts.dataset import DatasetSource
from app.datasets import canonical
from app.storage.jobflow import digest


def compile_prepared_source(engine, encounter_id, *, idempotency_key):
    service = engine.service
    encounter = engine.memory.get("source_encounter", encounter_id)
    case = SourceCase.model_validate(encounter["case"])
    with service.repository.transaction() as db:
        replay = service.repository.replay(
            db,
            f"request:{case.request_id}",
            idempotency_key,
            preparation_fingerprint(encounter_id),
            RequestDraft,
        )
        if replay:
            return replay
        draft = service.repository.load(db, "request", case.request_id, RequestDraft)
        registry_sources = service.registry.manifest(draft.corpus_id, db)
    result = encounter["result"]
    if result["status"] != "ready_for_customer_quote":
        raise ValueError("internal source ambiguity remains unresolved")
    refreshed = engine.assess(case)
    if refreshed["encounter_id"] != encounter_id:
        raise ValueError("source knowledge changed; review current preparation")
    normalized = DatasetSource.model_validate(result["normalized"])
    replaced_id = normalized.source_id
    # Unique draft-local identity, preserving the category suffix used by the
    # ordinary dataset compiler/verifier. Nothing becomes globally selectable.
    prepared_id = f"{case.source.corpus_id}:prepared:{case.request_id}:{normalized.category}"
    normalized = normalized.model_copy(
        update={
            "source_id": prepared_id,
            "version": 1,
        }
    )
    derived = evidence_source(
        case,
        normalized.category,
        service.store.put(canonical(normalized.model_dump(mode="json")), "application/json"),
    )
    attachments = [derived]
    if result["resolution_id"]:
        resolution = engine.memory.get("source_resolution", result["resolution_id"])
        attachments.append(
            evidence_source(
                case,
                "schema-resolution",
                Artifact.model_validate(resolution["evidence"]),
            )
        )
    lineage = service.store.put(
        canonical(
            {
                "origin": "explicitly_simulated_source_normalization",
                "source_binding": result["binding"],
                "column": result["column"],
                "procedure_id": result["procedure_id"],
                "resolution_id": result["resolution_id"],
                "derived": derived.model_dump(mode="json"),
                "citations": result["citations"],
                "encounter_id": encounter_id,
            }
        ),
        "application/json",
    )
    attachments.append(evidence_source(case, "schema-lineage", lineage))
    head = AuthorityHead.model_validate_json(service.store.read(case.authority.artifact))
    prepared = PreparedSources(
        encounter_id=encounter_id,
        registry_sources=registry_sources,
        sources=tuple(
            sorted(
                [s for s in registry_sources if s.source_id != replaced_id] + attachments,
                key=lambda s: s.source_id,
            )
        ),
        valid_until=head.valid_until,
    )
    return service.compile_request(
        case.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key=idempotency_key),
        prepared_sources=prepared,
    )


def evidence_source(case, name, artifact):
    return Source(
        source_id=f"{case.source.corpus_id}:prepared:{case.request_id}:{name}",
        version=1,
        corpus_id=case.source.corpus_id,
        supplier_id=case.source.supplier_id,
        edition=case.source.edition,
        effective_date=case.source.effective_date,
        artifact=artifact,
        authority="authorized_representative",
        authority_record=case.source.authority_record,
    )


def compile_composed_sources(
    engine,
    encounter_ids,
    *,
    idempotency_key,
    learning_version=None,
    compile_fingerprint=None,
):
    """Compose independently evidenced disjoint partitions, not cached answers."""
    service = engine.service
    records = [engine.memory.get("source_encounter", identifier) for identifier in encounter_ids]
    cases = [SourceCase.model_validate(record["case"]) for record in records]
    first = cases[0]
    if len(cases) < 2 or any(
        (case.request_id, case.customer_id, case.scope, case.source.supplier_id)
        != (first.request_id, first.customer_id, first.scope, first.source.supplier_id)
        for case in cases
    ):
        raise ValueError("composition needs related independently evidenced source partitions")
    identifier = "composition-" + digest({"encounters": encounter_ids, "version": learning_version})
    with service.repository.transaction() as db:
        replay = service.repository.replay(
            db,
            f"request:{first.request_id}",
            idempotency_key,
            compile_fingerprint or preparation_fingerprint(identifier),
            RequestDraft,
        )
        if replay:
            return replay
        draft = service.repository.load(db, "request", first.request_id, RequestDraft)
        registry = service.registry.manifest(draft.corpus_id, db)
    results = [engine.assess(case) for case in cases]
    if any(
        result["encounter_id"] != expected or result["status"] != "ready_for_customer_quote"
        for result, expected in zip(results, encounter_ids, strict=True)
    ):
        raise ValueError("composition evidence changed or remains unresolved")
    sources = [DatasetSource.model_validate(result["normalized"]) for result in results]
    rows = tuple(row for source in sources for row in source.rows)
    if len({row.zip for row in rows}) != len(rows):
        raise ValueError("source partitions overlap; summing counts is not authorized")
    normalized = sources[0].model_copy(
        update={
            "source_id": f"{draft.corpus_id}:prepared:{draft.request_id}:{first.scope.category}",
            "version": 1,
            "rows": tuple(sorted(rows, key=lambda row: row.zip)),
        }
    )
    derived = evidence_source(
        first,
        first.scope.category,
        service.store.put(
            canonical(normalized.model_dump(mode="json")),
            "application/json",
        ),
    )
    attachments = [derived]
    for index, result in enumerate(results):
        if result["resolution_id"]:
            resolution = engine.memory.get("source_resolution", result["resolution_id"])
            attachments.append(
                evidence_source(
                    first,
                    f"schema-resolution-{index}",
                    Artifact.model_validate(resolution["evidence"]),
                )
            )
    lineage = service.store.put(
        canonical(
            {
                "origin": "controlled_local_simulated_composition",
                "operations": [
                    "normalize_each_authorized_partition",
                    "reject_overlap",
                    "join_by_zip",
                ],
                "components": [
                    {
                        "encounter_id": r["encounter_id"],
                        "binding": r["binding"],
                        "citations": r["citations"],
                        "procedure_id": r["procedure_id"],
                    }
                    for r in results
                ],
                "learning_version": learning_version,
                "derived": derived.model_dump(mode="json"),
            }
        ),
        "application/json",
    )
    attachments.append(evidence_source(first, "schema-lineage", lineage))
    heads = [
        AuthorityHead.model_validate_json(service.store.read(c.authority.artifact)) for c in cases
    ]
    return service.compile_request(
        first.request_id,
        RevisionCommand(
            expected_revision=draft.revision,
            idempotency_key=idempotency_key,
        ),
        prepared_sources=PreparedSources(
            encounter_id=identifier,
            registry_sources=registry,
            sources=tuple(
                sorted(
                    [s for s in registry if s.source_id != sources[0].source_id] + attachments,
                    key=lambda s: s.source_id,
                )
            ),
            valid_until=min(head.valid_until for head in heads),
            learning_version=learning_version,
            compile_fingerprint=compile_fingerprint,
        ),
    )
