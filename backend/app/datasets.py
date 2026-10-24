"""Synthetic aggregate production and independent byte validation.

The accepted regional-data engine in data_products.py remains compatible. This
version reuses its frozen pins/provenance, adding integer cohorts and suppression.
No evaluator labels, generator switches or model verdicts enter validation.
"""

import csv
import hashlib
import io
import json
from datetime import date

from app.contracts.data_product import SourcePin, TermProvenance
from app.contracts.dataset import (
    DATASET_CHECKS,
    DATASET_COLUMNS,
    DATASET_CORPUS,
    PUBLIC_DATASET_JSON,
    CoverageUniverse,
    DatasetManifest,
    DatasetReference,
    DatasetRow,
    DatasetSource,
    DatasetSpecification,
)

SF_KEYS = (
    "94102",
    "94103",
    "94104",
    "94105",
    "94107",
    "94108",
    "94109",
    "94110",
    "94111",
    "94112",
    "94114",
    "94115",
    "94116",
    "94117",
    "94118",
    "94121",
    "94122",
    "94123",
    "94124",
    "94127",
    "94129",
    "94130",
    "94131",
    "94132",
    "94133",
    "94134",
    "94158",
)
OAKLAND_KEYS = (
    "94601",
    "94602",
    "94603",
    "94605",
    "94606",
    "94607",
    "94609",
    "94610",
    "94611",
    "94612",
    "94618",
    "94619",
    "94621",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def is_dataset(order):
    return isinstance(order.snapshot.quote.specification.terms, DatasetSpecification)


def delivery_artifact(delivery):
    return delivery.csv if hasattr(delivery, "csv") else delivery.pdf


def source_pin(source):
    return SourcePin(
        source_id=source.source_id, version=source.version, sha256=source.artifact.sha256
    )


def seed_registry(registry, store):
    """Public synthetic records only. Suppressed exact counts never exist in these fixtures."""
    from app.contracts.catalog import Source

    for corpus, geography, keys in (
        (DATASET_CORPUS, "San Francisco", SF_KEYS),
        ("oakland-aggregate-v1", "Oakland", OAKLAND_KEYS),
    ):
        records = {
            "coverage": {
                "kind": "coverage",
                "version": 1,
                "geography": geography,
                "authority_record": "synthetic-city-reference-v1",
                "boundary_notice": "Explicit synthetic ZIP inclusion; not real city boundaries.",
                "rows": [
                    {"zip": k, "area": "Mission" if k == "94110" else geography} for k in keys
                ],
            },
            "authority": {
                "kind": "authority",
                "version": 1,
                "authority_record": "synthetic-provider-registry-v1",
                "registered_publisher": "DatumCo synthetic vendor",
                "definition": "Gym membership or fitness-app use.",
                "yoga_is_gym": False,
                "yoga_category": "Wellness",
                "notice": "Synthetic authority evidence; no live attestation.",
            },
        }
        for category in ("gym_or_fitness_app", "gym_app_or_yoga"):
            source_id = f"{corpus}:{category}"
            records[category] = DatasetSource(
                source_id=source_id,
                edition="synthetic-2026-10",
                geography=geography,
                age_min=25,
                age_max=34,
                category=category,
                population="synthetic_adults",
                count_unit="unique_adults_per_zip",
                groups_disjoint=True,
                rows=tuple(
                    DatasetRow(
                        zip=k,
                        area="Mission" if k == "94110" else geography,
                        count=None
                        if k == "94129"
                        else 100 + i * 10 + (50 if category == "gym_app_or_yoga" else 0),
                        status="suppressed" if k == "94129" else "released",
                    )
                    for i, k in enumerate(keys)
                ),
            ).model_dump(mode="json")
        for name, content in records.items():
            content["source_id"] = f"{corpus}:{name}"
            registry.register(
                Source(
                    source_id=f"{corpus}:{name}",
                    version=1,
                    corpus_id=corpus,
                    supplier_id="DatumCo",
                    edition="synthetic-2026-10",
                    effective_date=date(2026, 10, 24),
                    artifact=store.put(canonical(content), "application/json"),
                    authority="registered_supplier_publication",
                    authority_record="synthetic-provider-registry-v1"
                    if name != "coverage"
                    else "synthetic-city-reference-v1",
                )
            )


def make_terms(sources, store, *, category="gym_or_fitness_app", request_id="synthetic-intake"):
    coverage = next(s for s in sources if s.source_id.endswith(":coverage"))
    data = json.loads(store.read(coverage.artifact))
    return DatasetSpecification(
        corpus_id=coverage.corpus_id,
        geography=data["geography"],
        category=category,
        category_meaning="Gym membership or fitness-app use; standalone yoga is excluded."
        if category == "gym_or_fitness_app"
        else "Gym membership, fitness-app use or yoga-studio membership.",
        coverage=CoverageUniverse(
            pin=source_pin(coverage),
            geography=data["geography"],
            expected_keys=tuple(r["zip"] for r in data["rows"]),
            authority_record=coverage.authority_record,
        ),
        sources=tuple(source_pin(s) for s in sources),
        provenance=(
            TermProvenance(
                reference_id=request_id, origin="customer_answer", actor_id="AcmeFitness"
            ),
        ),
    )


def requirement_words(terms):
    return {
        "cohort": "Synthetic adults aged 25–34; unique adults, disjoint ZIP groups.",
        "category": terms.category_meaning,
        "geography": f"{terms.geography} using the frozen synthetic ZIP inclusion registry.",
        "schema": "CSV columns: zip, area, count, status; stable ZIP row identities.",
        "coverage": (
            "Every frozen registry ZIP exactly once; no duplicate, extra or silently missing rows."
        ),
        "suppression": (
            "Released integer counts ≥50; suppressed rows retained with null "
            "counts; unknown is distinct."
        ),
        "provenance": "Exact registered dataset editions, hashes and authority records.",
        "artifact": "Downloaded CSV and JSON preview agree with the independently checked sources.",
    }


def reference(
    artifact,
    source_id,
    *,
    row="$",
    column="kind",
    value=None,
    version=1,
    expected=None,
    coverage=None,
):
    return DatasetReference(
        artifact_id=artifact.artifact_id,
        sha256=artifact.sha256,
        source_id=source_id,
        version=version,
        row=row,
        column=column,
        value=value,
        expected_key=expected,
        coverage_sha256=coverage,
    )


def resolve_reference(ref, artifacts, store):
    artifact = next(
        (a for a in artifacts if a.artifact_id == ref.artifact_id and a.sha256 == ref.sha256), None
    )
    if artifact is None:
        raise ValueError("dataset reference is outside the supplied evidence")
    raw = public_bytes(artifact, store)
    if artifact.media_type == "text/csv":
        data = {"rows": list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))}
    else:
        data = json.loads(raw)
    if (
        data.get("source_id", ref.source_id) != ref.source_id
        or data.get("version", ref.version) != ref.version
    ):
        raise ValueError("reference source identity or version does not match its bytes")
    if ref.expected_key is not None:
        coverage = next((a for a in artifacts if a.sha256 == ref.coverage_sha256), None)
        if coverage is None or ref.expected_key not in {
            r["zip"] for r in json.loads(public_bytes(coverage, store))["rows"]
        }:
            raise ValueError("absence lacks frozen coverage evidence")
        if any(r.get("zip") == ref.expected_key for r in data.get("rows", [])):
            raise ValueError("claimed absent row exists")
        actual = None
    elif ref.row == "$":
        actual = data.get(ref.column)
    else:
        matches = [r for r in data.get("rows", []) if r.get("zip") == ref.row]
        if len(matches) != 1 or ref.column not in matches[0]:
            raise ValueError("dataset cell does not resolve uniquely")
        row = matches[0]
        if row.get("status") != "released" and ref.column == "count":
            actual = None
        else:
            actual = row[ref.column]
    value = (
        None
        if actual is None
        else (str(actual).lower() if isinstance(actual, bool) else str(actual))
    )
    if value != ref.value:
        raise ValueError("dataset citation differs from immutable bytes")
    return value


def parse_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    if tuple(reader.fieldnames or ()) != DATASET_COLUMNS:
        raise ValueError("CSV schema mismatch")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("CSV row width mismatch")
        value = row["count"]
        if value and (not value.isascii() or not value.isdigit()):
            raise ValueError("count must be a nonnegative integer")
        rows.append(
            DatasetRow(
                zip=row["zip"],
                area=row["area"],
                count=int(value) if value else None,
                status=row["status"],
            )
        )
    return tuple(rows)


def produce_dataset(terms, sources, store):
    source = next(s for s in sources if s.source_id.endswith(":" + terms.category))
    data = DatasetSource.model_validate_json(store.read(source.artifact))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=DATASET_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in data.rows:
        writer.writerow(row.model_dump())
    csv_artifact = store.put(out.getvalue().encode(), "text/csv")
    manifest = DatasetManifest(
        csv_sha256=csv_artifact.sha256,
        specification_sha256=digest(canonical(terms.model_dump(mode="json"))),
        sources=terms.sources,
        coverage=terms.coverage.pin,
        rows=data.rows,
    )
    preview = store.put(manifest.model_dump_json().encode(), "application/json")
    return csv_artifact, preview


def verify_dataset(context, store, now, *, delivery=None, preview=None, stage="fulfillment"):
    """Reopen source, coverage, CSV and preview bytes; never trust producer verdicts."""
    from app.contracts.catalog import Assessment, Obligation, Provenance, Verification

    terms = context.snapshot.quote.specification.terms
    sources = context.sources
    obligations = tuple(
        Obligation(
            obligation_id=f"dataset:{k}",
            requirement_id=f"R-{k.upper()}",
            subject="dataset",
            field=k,
            check=k,
            dependencies=() if k == "provenance" else ("dataset:provenance",),
        )
        for k in DATASET_CHECKS
    )
    results = {k: "PASS" for k in DATASET_CHECKS}
    explanations = requirement_words(terms)
    source = next((s for s in sources if s.source_id.endswith(":" + terms.category)), None)
    coverage = next((s for s in sources if s.source_id == terms.coverage.pin.source_id), None)
    authority = next((s for s in sources if s.source_id.endswith(":authority")), None)
    refs = {k: [] for k in DATASET_CHECKS}
    for k in DATASET_CHECKS:
        if coverage:
            refs[k].append(
                reference(
                    coverage.artifact,
                    coverage.source_id,
                    column="geography",
                    value=terms.geography,
                    version=coverage.version,
                )
            )

    def fail(key, text, result="FAIL"):
        results[key], explanations[key] = result, text

    data = None
    expected_rows = None
    try:
        if tuple(source_pin(s) for s in sources) != terms.sources:
            fail("provenance", "Current source pins differ from the accepted manifest.", "CONFLICT")
        for s in sources:
            store.read(s.artifact)
            if s.authority == "unverified" or not s.authority_record:
                fail(
                    "provenance", "Registered source authority has not been established.", "UNKNOWN"
                )
        if not source or not coverage or not authority:
            raise ValueError("missing registered source")
        registry = json.loads(store.read(coverage.artifact))
        auth = json.loads(store.read(authority.artifact))
        if auth.get("authority_record") != authority.authority_record or not auth.get(
            "registered_publisher"
        ):
            fail(
                "provenance",
                "Authority record does not establish the selected publisher.",
                "UNKNOWN",
            )
        if (
            source_pin(coverage) != terms.coverage.pin
            or registry.get("authority_record") != terms.coverage.authority_record
        ):
            fail(
                "provenance",
                "Coverage authority or edition conflicts with the accepted registry.",
                "CONFLICT",
            )
        registry_keys = tuple(r["zip"] for r in registry["rows"])
        if registry_keys != terms.coverage.expected_keys:
            fail(
                "coverage",
                "Coverage denominator differs from the frozen authoritative keys.",
                "CONFLICT",
            )
        raw_source = json.loads(store.read(source.artifact))
        # Validate redaction before any raw values can reach citations or public events.
        data = DatasetSource.model_validate(raw_source)
        expected_rows = data.rows
        for key, column in (
            ("cohort", "age_min"),
            ("category", "category"),
            ("geography", "geography"),
            ("provenance", "edition"),
        ):
            refs[key].append(
                reference(
                    source.artifact,
                    source.source_id,
                    column=column,
                    value=str(raw_source[column]),
                    version=source.version,
                )
            )
        if (data.age_min, data.age_max, data.population, data.count_unit, data.groups_disjoint) != (
            terms.age_min,
            terms.age_max,
            terms.population,
            terms.count_unit,
            True,
        ):
            fail(
                "cohort",
                (
                    "Source cohort age, population, count unit or disjointness "
                    "differs from the agreement."
                ),
            )
        if data.category != terms.category:
            fail("category", "Source category differs from the accepted definition.")
        if data.geography != terms.geography or registry["geography"] != terms.geography:
            fail("geography", "Source or coverage geography differs from the agreement.")
        if (
            data.source_id != source.source_id
            or data.version != source.version
            or data.edition != source.edition
        ):
            fail(
                "provenance",
                "Source identity or edition differs from its registered pin.",
                "CONFLICT",
            )
    except Exception:
        fail(
            "provenance",
            "Accepted source/coverage bytes are unavailable, malformed or inconsistent.",
            "UNKNOWN",
        )
        fail(
            "suppression",
            "Source counts cannot be safely released under the accepted schema.",
            "UNKNOWN",
        )
    source_ok = all(v == "PASS" for v in results.values())

    def coverage_check(rows, artifact, source_id, version=1):
        keys = [r.zip for r in rows]
        missing = set(terms.coverage.expected_keys) - set(keys)
        if missing or len(keys) != len(set(keys)) or set(keys) != set(terms.coverage.expected_keys):
            fail("coverage", "Missing, duplicate or unexpected ZIPs against the frozen registry.")
            for key in sorted(missing):
                refs["coverage"].append(
                    reference(
                        artifact,
                        source_id,
                        row=key,
                        column="zip",
                        expected=key,
                        version=version,
                        coverage=terms.coverage.pin.sha256,
                    )
                )
        if any(r.status == "unknown" for r in rows):
            fail(
                "coverage",
                "Unknown counts remain unresolved; suppression is a separate status.",
                "UNKNOWN",
            )

    if data:
        coverage_check(data.rows, source.artifact, source.source_id)
    source_ok = source_ok and all(v == "PASS" for v in results.values())
    provider_defect = False
    if delivery is not None:
        try:
            raw = store.read(delivery)
            rows = parse_csv(raw)
            coverage_check(rows, delivery, "delivery", context.binding.delivery_version)
            if rows:
                refs["artifact"].append(
                    reference(
                        delivery,
                        "delivery",
                        row=rows[0].zip,
                        column="zip",
                        value=rows[0].zip,
                        version=context.binding.delivery_version,
                    )
                )
            manifest = DatasetManifest.model_validate_json(store.read(preview))
            if (
                manifest.rows != rows
                or manifest.csv_sha256 != digest(raw)
                or manifest.sources != terms.sources
                or manifest.coverage != terms.coverage.pin
                or manifest.columns != DATASET_COLUMNS
                or manifest.specification_sha256 != digest(canonical(terms.model_dump(mode="json")))
            ):
                fail("artifact", "Downloaded CSV and structured preview/manifest do not agree.")
            if expected_rows is not None and rows != expected_rows:
                fail(
                    "artifact",
                    "Delivered rows differ from independently parsed accepted source values.",
                )
            provider_defect = source_ok and any(v == "FAIL" for v in results.values())
        except Exception:
            fail(
                "schema",
                "Delivered CSV or JSON bytes are unavailable or violate the agreed schema.",
            )
            fail(
                "artifact",
                "Independent byte validation failed; no producer report can establish correctness.",
            )
            provider_defect = source_ok
    elif stage != "fulfillment":
        fail("artifact", "No delivered bytes or preview were provided.", "UNKNOWN")
    assessments = []
    for key in DATASET_CHECKS:
        valid_refs = []
        for ref in refs[key]:
            try:
                resolve_reference(
                    ref,
                    tuple(s.artifact for s in sources) + tuple(a for a in (delivery, preview) if a),
                    store,
                )
                valid_refs.append(ref)
            except Exception:
                pass
        result = results[key]
        if not valid_refs:
            result = "UNKNOWN"
        assessments.append(
            Assessment(
                obligation_id=f"dataset:{key}",
                result=result,
                citations=tuple(valid_refs),
                conflicting_evidence=tuple(valid_refs) if result == "CONFLICT" else (),
                missing_facts=(explanations[key],) if result == "UNKNOWN" else (),
                reason_code=f"DATASET_{key.upper()}_{result}",
                explanation=explanations[key],
                requested_evidence=(
                    "Provide the registered authority/edition establishing the "
                    "disputed definition or missing key."
                )
                if result in ("UNKNOWN", "CONFLICT")
                else None,
                provenance=Provenance(
                    kind="deterministic", assessor="aggregate-byte-validator", version="1"
                ),
            )
        )
    blockers = tuple(a.obligation_id for a in assessments if a.result in ("UNKNOWN", "CONFLICT"))
    return Verification(
        binding=context.binding,
        stage=stage,
        obligations=obligations,
        assessments=tuple(assessments),
        material_blockers=blockers,
        provider_defect=provider_defect,
        passed=all(a.result == "PASS" for a in assessments),
        created_at=now,
    ), ()


def public_bytes(artifact, store):
    """Fail closed on unsafe count-bearing artifacts, including rejected source fixtures."""
    from app.orders.service import DomainError

    raw = store.read(artifact)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON property")
            result[key] = value
        return result

    try:
        if artifact.media_type == "text/csv":
            parse_csv(raw)
        elif artifact.media_type == "application/json":
            PUBLIC_DATASET_JSON.validate_python(json.loads(raw, object_pairs_hook=unique_object))
        else:
            raise ValueError("not a dataset artifact")
    except (ValueError, KeyError, TypeError):
        raise DomainError(409, "Artifact is withheld: safe aggregate validation failed") from None
    return raw
