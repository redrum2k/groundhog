"""Explicitly simulated source-owner experience, never real commercial incidents.

The ambiguous columns deliberately have overlapping plausible numeric ranges.
Only the simulated provider's separately supplied definition establishes meaning.
Production code never imports this module or receives its expected column.
"""

from datetime import timedelta

from app.agents.source_knowledge import (
    AuthorityHead,
    Definition,
    InstitutionalMemory,
    ResolutionEvidence,
    SourceCase,
    SourceKnowledge,
    SourceScope,
    VendorExport,
    VendorRow,
)
from app.contracts.catalog import RequestCommand, Source
from app.datasets import SF_KEYS, canonical, seed_registry, source_pin

OWNER = "simulated:DatumCo-schema-owner"
CUSTOMER = "AcmeFitness:operational-sandbox"
PUBLISHER = "DatumCo"
CORPUS = "sf-aggregate-v1"


def source(service, source_id, version, content, edition="simulated-vendor-edition-1"):
    return Source(
        source_id=source_id,
        version=version,
        corpus_id=CORPUS,
        supplier_id=PUBLISHER,
        edition=edition,
        effective_date=service.clock().date(),
        artifact=service.store.put(canonical(content), "application/json"),
        authority="registered_supplier_publication",
        authority_record="simulated-source-owner-v1",
    )


def setup_source(
    service,
    *,
    columns=("m17", "m42"),
    source_version=1,
    head_version=1,
    epoch="dictionary-1",
    status="active",
    definitions=(),
    expired=False,
    reverse=False,
    batch=1,
):
    seed_registry(service.registry, service.store)
    scope = SourceScope(geography="San Francisco")
    raw = VendorExport(
        source_id=CORPUS + f":vendor-export-batch-{batch}",
        source_family="DatumCo-fitness-export",
        schema_version=source_version,
        version=source_version,
        publisher=PUBLISHER,
        edition=f"simulated-vendor-edition-{source_version}",
        scope=scope,
        columns=columns,
        rows=tuple(
            VendorRow(
                zip=key,
                area="Mission" if key == "94110" else "San Francisco",
                values={
                    columns[0]: None
                    if key == "94129"
                    else 130 + i * 7 + (100 if reverse else 0) + 13 * (batch - 1),
                    columns[1]: None
                    if key == "94129"
                    else 230 + i * 7 - (100 if reverse else 0) + 17 * (batch - 1),
                },
                status="suppressed" if key == "94129" else "released",
            )
            for i, key in enumerate(SF_KEYS)
        ),
    )
    raw_source = source(
        service, raw.source_id, raw.version, raw.model_dump(mode="json"), raw.edition
    )
    # A new intake selects the new vendor batch. Prior private exception attachments
    # remain in immutable accepted snapshots/history, not current published docs.
    with service.repository.transaction() as db:
        db.execute(
            "UPDATE catalog_sources SET selectable=0 WHERE source_id LIKE ? AND source_id != ?",
            (CORPUS + ":vendor-export-batch-%", raw.source_id),
        )
        db.execute(
            "UPDATE catalog_sources SET selectable=0 WHERE source_id IN (?,?)",
            (CORPUS + ":schema-resolution", CORPUS + ":schema-lineage"),
        )
    service.registry.register(raw_source)
    head = AuthorityHead(
        publisher=PUBLISHER,
        source_id=raw.source_family,
        source_version=raw.schema_version,
        schema_hash=raw.schema_hash,
        epoch=epoch,
        scope=scope,
        status=status,
        valid_until=service.clock() + timedelta(hours=-1 if expired else 2),
        definitions=tuple(Definition(column=c, unit=u) for c, u in definitions),
    )
    authority = source(
        service,
        CORPUS + ":schema-authority",
        head_version,
        head.model_dump(mode="json"),
        raw.edition,
    )
    service.registry.register(authority)
    return raw_source, authority, raw


def make_case(service, inputs, name, zips=("94102",), customer=CUSTOMER):
    raw_source, authority, raw = inputs
    draft = service.create_request(
        RequestCommand(
            prompt="SF adults 25-34, gym members or fitness app users, counts by ZIP. "
            + "For source checking focus on ZIPs "
            + ", ".join(zips)
            + ".",
            corpus_id=CORPUS,
            idempotency_key=name,
        )
    )
    return SourceCase(
        case_id=name,
        request_id=draft.request_id,
        customer_id=customer,
        source=raw_source,
        authority=authority,
        scope=raw.scope,
        requested_zips=zips,
    )


def engine(service, book, *, customer=CUSTOMER):
    memory = InstitutionalMemory(service.repository.path, customer, book, sandbox=True)
    return SourceKnowledge(service, memory, {OWNER: PUBLISHER}, sandbox=True)


def resolution_evidence(service, case, raw, column, *, actor=OWNER, applicability="source_edition"):
    proof = ResolutionEvidence(
        origin="explicitly_simulated_provider_resolution",
        actor_id=actor,
        publisher=PUBLISHER,
        source_family=raw.source_family,
        schema_version=raw.schema_version,
        source_pin=source_pin(case.source).model_dump(mode="json"),
        authority_pin=source_pin(case.authority).model_dump(mode="json"),
        schema_hash=raw.schema_hash,
        scope=case.scope,
        applicability=applicability,
        definition=Definition(column=column, unit=case.desired_unit),
        explanation="Simulated source owner confirms this column counts distinct eligible adults "
        "per ZIP across batches of this exact source-family schema edition. "
        "The other column counts repeat observations.",
    )
    return service.store.put(canonical(proof.model_dump(mode="json")), "application/json")
