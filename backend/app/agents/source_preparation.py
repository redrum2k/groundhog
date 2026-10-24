"""Sandbox bridge: prepared source -> ordinary draft quote, never implicit consent.

Source normalization and its raw/authority/lineage pins enter the existing quote.
No accepted snapshot or payment path is modified. Caller must subsequently use
normal explicit acceptance and funding, exactly as without institutional memory.
"""

from app.agents.source_knowledge import SourceCase
from app.contracts.catalog import Artifact, RevisionCommand, Source
from app.contracts.dataset import DatasetSource
from app.datasets import canonical


def compile_prepared_source(engine, encounter_id, *, idempotency_key):
    service = engine.service
    encounter = engine.memory.get("source_encounter", encounter_id)
    case = SourceCase.model_validate(encounter["case"])
    result = encounter["result"]
    if result["status"] != "ready_for_customer_quote":
        raise ValueError("internal source ambiguity remains unresolved")
    # Re-run the same current evidence checks; a stale result cannot be published.
    refreshed = engine.assess(case)
    if refreshed["encounter_id"] != encounter_id:
        raise ValueError("source knowledge changed; review current preparation")
    normalized = DatasetSource.model_validate(result["normalized"])
    # Registered editions are immutable. Allocate a new derived edition only if
    # its actual content differs; retries reuse the same registered source.
    existing = next(
        s
        for s in service.registry.manifest(case.source.corpus_id)
        if s.source_id == normalized.source_id
    )
    prior = DatasetSource.model_validate_json(service.store.read(existing.artifact))
    if prior.model_dump(exclude={"version"}) == normalized.model_dump(exclude={"version"}):
        derived = existing
    else:
        normalized = normalized.model_copy(update={"version": existing.version + 1})
        derived = Source(
            source_id=normalized.source_id,
            version=normalized.version,
            corpus_id=case.source.corpus_id,
            supplier_id=case.source.supplier_id,
            edition=normalized.edition,
            effective_date=case.source.effective_date,
            artifact=service.store.put(
                canonical(normalized.model_dump(mode="json")), "application/json"
            ),
            authority="authorized_representative",
            authority_record=case.source.authority_record,
        )
        service.registry.register(derived)
    # Attach the previous resolution itself (when used) and derivation to the
    # selected registry so ordinary acceptance freezes all the supporting bytes.
    if result["resolution_id"]:
        resolution = engine.memory.get("source_resolution", result["resolution_id"])
        proof = Artifact.model_validate(resolution["evidence"])
        register_evidence(service, case, "schema-resolution", proof)
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
    register_evidence(service, case, "schema-lineage", lineage)
    draft = service.get_request(case.request_id)
    return service.compile_request(
        case.request_id,
        RevisionCommand(
            expected_revision=draft.revision,
            idempotency_key=idempotency_key,
        ),
    )


def register_evidence(service, case, name, artifact):
    source_id = case.source.corpus_id + ":" + name
    # Private evidence from a previous intake can be non-selectable, but its version
    # number remains reserved. Never overwrite an old accepted evidence edition.
    with service.repository.transaction() as db:
        row = db.execute(
            "SELECT max(version) FROM catalog_sources WHERE source_id=?", (source_id,)
        ).fetchone()
    version = (row[0] or 0) + 1
    return service.registry.register(
        Source(
            source_id=source_id,
            version=version,
            corpus_id=case.source.corpus_id,
            supplier_id=case.source.supplier_id,
            edition=case.source.edition,
            effective_date=case.source.effective_date,
            artifact=artifact,
            authority="authorized_representative",
            authority_record=case.source.authority_record,
        )
    )
