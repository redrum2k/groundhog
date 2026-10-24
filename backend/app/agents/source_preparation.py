"""Sandbox bridge to ordinary compilation with draft-local source/evidence pins.

No shared registry publication, accepted snapshot mutation or implicit consent.
"""

from app.agents.source_knowledge import AuthorityHead, SourceCase
from app.catalog.preparation import PreparedSources, preparation_fingerprint
from app.contracts.catalog import Artifact, RequestDraft, RevisionCommand, Source
from app.contracts.dataset import DatasetSource
from app.datasets import canonical


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
