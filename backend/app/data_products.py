"""Small deterministic data-contract engine and actual versioned deliverables."""

import csv
import hashlib
import io
import json
from datetime import timedelta
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.contracts.data_product import (
    DataCitation,
    DataSpecification,
    Parameters,
    Requirement,
    RequirementAssessment,
    SourcePin,
    SourceSnapshot,
    TermProvenance,
)
from app.investigation.documents import extract_document
from app.storage.jobflow import canonical, digest

DIMENSIONS = {
    "freshness": ("age_within_days", ("freshness_basis", "max_age_days", "as_of")),
    "geography": ("region_version", ("geography", "boundary_version", "region_ids")),
    "reference_period": ("period_equals", ("reference_period",)),
    "metric": ("metric_equals", ("metric_name", "metric_unit")),
    "entity_unit": ("unique_entity", ("entity_unit",)),
    "coverage": ("coverage_ids", ("coverage_ids", "max_missing_records")),
    "source_lineage": ("exact_sources", ("revision_policy", "conflict_policy")),
    "output_schema": ("market_schema_v1", ("output_schema", "output_format")),
}
FIELDS = tuple(field for _, fields in DIMENSIONS.values() for field in fields)
BASE_FIELDS = tuple(field for field in FIELDS if field not in DIMENSIONS["freshness"][1])
QUESTION_TEXT = {
    "freshness_basis": "Does freshness mean observation date, publication date, or export date?",
    "max_age_days": "What maximum age in days is acceptable on the agreed as-of date?",
    "as_of": "What timezone-aware as-of date should the freshness check use?",
    "geography": "Which named geographic area is required (for example city or metro)?",
    "boundary_version": "Which published geographic boundary revision should apply?",
    "region_ids": "Which exact region codes belong to the agreed geography?",
    "reference_period": "Which observation/reference period does the requested statistic describe?",
    "metric_name": "Which metric definition is intended: household or individual income?",
    "metric_unit": "What measurement unit applies to that metric?",
    "entity_unit": "Is each record a region, establishment, legal entity, household, or person?",
    "coverage_ids": "List every expected entity ID: the denominator, not just delivered rows.",
    "max_missing_records": "How many of those expected records may be missing?",
    "revision_policy": "Confirm exact_accepted_versions: both parties accept source versions.",
    "conflict_policy": "Confirm UNKNOWN: conflicting source authority requires review.",
    "output_schema": "Confirm market-v1: entity_id, region_id, value, observed_at, source lineage.",
    "output_format": "Choose json or csv for the data. A methodology PDF is also included.",
}


def parse_source(raw: bytes) -> SourceSnapshot:
    extract_document(raw, "source.json", "application/json")
    return SourceSnapshot.model_validate_json(raw)


def source_pin(raw: bytes) -> SourcePin:
    source = parse_source(raw)
    return SourcePin(
        source_id=source.source_id, version=source.version, sha256=hashlib.sha256(raw).hexdigest()
    )


def missing_fields(parameters: Parameters) -> list[str]:
    return [
        field
        for field in FIELDS
        if getattr(parameters, field) is None or getattr(parameters, field) == ()
    ]


def make_specification(draft) -> DataSpecification:
    provenance = tuple(
        TermProvenance(
            reference_id=m.id,
            actor_id=m.actor_id,
            origin="customer_answer" if m.field else "original_intent",
        )
        for m in draft.messages
    )
    requirements = []
    for dimension, (recipe, fields) in DIMENSIONS.items():
        parameters = Parameters.model_validate(
            {field: getattr(draft.parameters, field) for field in fields}
        )
        requirements.append(
            Requirement(
                id=f"req-{dimension}",
                dimension=dimension,
                meaning=(
                    f"Customer-confirmed {dimension.replace('_', ' ')} for: "
                    f"{draft.messages[0].text[:800]}"
                ),
                recipe=draft.validator_bindings.get(dimension, recipe),
                parameters=parameters,
                provenance=provenance
                + (
                    (
                        TermProvenance(
                            reference_id=draft.template_version,
                            origin="approved_template",
                            actor_id=draft.template_approved_by,
                        ),
                    )
                    if dimension in draft.validator_bindings and draft.template_approved_by
                    else ()
                ),
            )
        )
    return DataSpecification(
        product_id=draft.product_id,
        template_version=draft.template_version,
        original_intent=draft.messages[0].text,
        requirements=tuple(requirements),
        sources=tuple(draft.sources),
    )


def specification_digest(specification):
    return digest(specification.model_dump(mode="json"))


def source_checks(specification: DataSpecification, sources: list[bytes]):
    parsed = [(parse_source(raw), source_pin(raw)) for raw in sources]
    checks = []
    for requirement in specification.requirements:
        p = requirement.parameters
        expected_recipe, fields = DIMENSIONS.get(requirement.dimension, ("unsupported", ()))
        absent = [field for field in fields if getattr(p, field) is None or getattr(p, field) == ()]
        if requirement.recipe != expected_recipe or requirement.recipe == "unsupported":
            checks.append(
                RequirementAssessment(
                    requirement_id=requirement.id,
                    verdict="UNKNOWN",
                    cause="UNSUPPORTED_SUBJECTIVE",
                    explanation="No approved validator represents this accepted requirement.",
                )
            )
            continue
        if absent:
            checks.append(
                RequirementAssessment(
                    requirement_id=requirement.id,
                    verdict="UNKNOWN",
                    cause="MISSING_SPECIFICATION",
                    explanation="Accepted terms do not define: " + ", ".join(absent),
                )
            )
            continue
        if not parsed:
            checks.append(
                RequirementAssessment(
                    requirement_id=requirement.id,
                    verdict="UNKNOWN",
                    cause="MISSING_EVIDENCE",
                    explanation="Authenticated source snapshots are unavailable.",
                )
            )
            continue
        citations = []
        states = []
        details = []
        cause = "NONE"
        for source, pin in parsed:

            def cite(locator, value, pin=pin, citations=citations):
                citations.append(
                    DataCitation(**pin.model_dump(), locator=locator, value=str(value)[:1600])
                )

            if pin not in specification.sources:
                states.append("UNKNOWN")
                cause = "CONFLICTING_AUTHORITY"
                details.append("Source version/hash is not accepted.")
                continue
            match requirement.recipe:
                case "age_within_days":
                    for index, row in enumerate(source.rows):
                        observed = (
                            row.observed_at
                            if p.freshness_basis == "observed_at"
                            else getattr(source, p.freshness_basis)
                        )
                        locator = (
                            f"/rows/{index}/observed_at"
                            if p.freshness_basis == "observed_at"
                            else f"/{p.freshness_basis}"
                        )
                        cite(locator, observed.isoformat() if observed else "null")
                        if observed is None:
                            states.append("UNKNOWN")
                            cause = "MISSING_EVIDENCE"
                        else:
                            age = p.as_of - observed
                            states.append(
                                "PASS"
                                if timedelta(0) <= age <= timedelta(days=p.max_age_days)
                                else "FAIL"
                            )
                    details.append(
                        f"Compared {p.freshness_basis} with the accepted "
                        f"{p.max_age_days}-day limit and as-of date."
                    )
                case "region_version":
                    cite("/geography", source.geography)
                    cite("/boundary_version", source.boundary_version)
                    for index, row in enumerate(source.rows):
                        cite(f"/rows/{index}/region_id", row.region_id)
                    states.append(
                        "PASS"
                        if source.geography == p.geography
                        and source.boundary_version == p.boundary_version
                        and all(row.region_id in p.region_ids for row in source.rows)
                        else "FAIL"
                    )
                    details.append(
                        "Compared named geography, boundary revision and every region code."
                    )
                case "period_equals":
                    cite("/reference_period", source.reference_period)
                    states.append(
                        "PASS" if source.reference_period == p.reference_period else "FAIL"
                    )
                    details.append("Compared reference period, independently of file export date.")
                case "metric_equals":
                    cite("/metric_name", source.metric_name)
                    cite("/metric_unit", source.metric_unit)
                    states.append(
                        "PASS"
                        if (source.metric_name, source.metric_unit)
                        == (p.metric_name, p.metric_unit)
                        else "FAIL"
                    )
                    details.append("Compared the agreed statistical meaning and unit.")
                case "unique_entity":
                    cite("/entity_unit", source.entity_unit)
                    ids = [row.entity_id for row in source.rows]
                    cite("/rows/*/entity_id", ids)
                    all_ids = [row.entity_id for other, _ in parsed for row in other.rows]
                    variants = {}
                    for other, _ in parsed:
                        for row in other.rows:
                            variants.setdefault(row.entity_id, set()).add(
                                canonical(row.model_dump(mode="json"))
                            )
                    if source.entity_unit != p.entity_unit or len(ids) != len(set(ids)):
                        states.append("FAIL")
                    elif any(len(values) > 1 for values in variants.values()):
                        states.append("UNKNOWN")
                        cause = "CONFLICTING_AUTHORITY"
                    else:
                        states.append("PASS" if len(all_ids) == len(set(all_ids)) else "FAIL")
                    details.append("Checked uniqueness under the accepted entity unit.")
                case "coverage_ids":
                    ids = {row.entity_id for other, _ in parsed for row in other.rows}
                    missing = set(p.coverage_ids) - ids
                    extra = ids - set(p.coverage_ids)
                    cite("/rows/*/entity_id", [row.entity_id for row in source.rows])
                    states.append(
                        "PASS" if len(missing) <= p.max_missing_records and not extra else "FAIL"
                    )
                    details.append(
                        f"Coverage denominator={len(set(p.coverage_ids))}; "
                        f"missing={len(missing)}; unexpected={len(extra)}."
                    )
                case "exact_sources":
                    cite("/source_id", source.source_id)
                    cite("/version", source.version)
                    variants = {}
                    for other, _ in parsed:
                        for row in other.rows:
                            variants.setdefault(row.entity_id, set()).add(
                                canonical(row.model_dump(mode="json"))
                            )
                    if any(len(values) > 1 for values in variants.values()):
                        states.append("UNKNOWN")
                        cause = "CONFLICTING_AUTHORITY"
                        details.append("Accepted sources disagree; neither is silently selected.")
                    elif set(pin for _, pin in parsed) != set(specification.sources):
                        states.append("UNKNOWN")
                        cause = "MISSING_EVIDENCE"
                        details.append("One or more accepted sources are missing.")
                    else:
                        states.append("PASS")
                        details.append(
                            "All exact accepted source hashes and revisions are present."
                        )
                case "market_schema_v1":
                    cite("/rows", f"{len(source.rows)} typed source records")
                    states.append("PASS")
                    details.append(
                        "Source schema is supported; actual delivery is checked separately."
                    )
        verdict = (
            "FAIL"
            if "FAIL" in states
            else "UNKNOWN"
            if "UNKNOWN" in states or not states
            else "PASS"
        )
        if verdict == "FAIL":
            cause = "PROVIDER_DEFECT"
        if verdict == "PASS":
            cause = "NONE"
        checks.append(
            RequirementAssessment(
                requirement_id=requirement.id,
                verdict=verdict,
                cause=cause,
                explanation=" ".join(dict.fromkeys(details))[:1600]
                or "Source evidence does not establish the requirement.",
                citations=tuple(citations),
            )
        )
    return tuple(checks)


def dataset(sources):
    rows = []
    for raw in sources:
        source, pin = parse_source(raw), source_pin(raw)
        for row in source.rows:
            rows.append({**row.model_dump(mode="json"), **pin.model_dump()})
    if len(rows) > 250:
        raise ValueError("The bounded market profile supports at most 250 source rows per order")
    return {"schema": "market-v1", "rows": rows}


def report_lines(specification, data, checks):
    lines = [
        "REGIONAL MARKET INTELLIGENCE",
        "Aggregate data product - local mock settlement",
        f"Product: {specification.product_id}",
        f"Specification SHA256: {specification_digest(specification)}",
        "Method: preserve accepted source values and revisions; "
        "no scraping, imputation or personal-data enrichment.",
    ]
    lines.append("Accepted definitions")
    for requirement in specification.requirements:
        values = requirement.parameters.model_dump(mode="json", exclude_none=True)
        values = {key: value for key, value in values.items() if value != []}
        lines.append(f"{requirement.dimension}: {canonical(values)}")
    lines.append("Source provenance")
    for source in specification.sources:
        lines.append(f"{source.source_id} | version {source.version} | SHA256 {source.sha256}")
    lines.append("Acceptance checks and exceptions")
    for check in checks:
        lines.append(f"{check.requirement_id}: {check.verdict} | {check.explanation}")
    lines.append("Delivered records")
    for index, row in enumerate(data["rows"], 1):
        lines.append(
            f"Row {index}: {row['entity_id']} | region {row['region_id']} | value {row['value']} | "
            f"observed {row['observed_at']} | source {row['source_id']} v{row['version']}"
        )
    return lines


def build_package(specification, sources):
    data = dataset(sources)
    checks = source_checks(specification, sources)
    output = next(
        (
            r.parameters.output_format
            for r in specification.requirements
            if r.dimension == "output_schema"
        ),
        "json",
    )
    structured = canonical(data).encode()
    if output == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(data["rows"][0]))
        writer.writeheader()
        writer.writerows(data["rows"])
        data_raw, media, filename = buffer.getvalue().encode(), "text/csv", "market-data.csv"
    else:
        data_raw, media, filename = structured, "application/json", "market-data.json"
    pdf = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf,
        pagesize=letter,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title="Regional market intelligence",
        author="OBJECTION",
    )
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 13
    styles["BodyText"].textColor = colors.HexColor("#24364B")
    story = []
    for index, line in enumerate(report_lines(specification, data, checks)):
        style = styles["Title"] if index == 0 else styles["BodyText"]
        story.extend([Paragraph(escape(line), style), Spacer(1, 7)])
    doc.build(story)
    return [
        (filename, media, data_raw),
        ("source-methodology.pdf", "application/pdf", pdf.getvalue()),
        ("market-sidecar.json", "application/json", structured),
    ]


def delivery_checks(specification, sources, artifacts):
    """Reopen actual bytes; no producer success flag can establish delivery correctness."""
    checks = []
    expected = dataset(sources)
    source_result = source_checks(specification, sources)
    required_lines = report_lines(specification, expected, source_result)
    for filename, media, raw, artifact_id in artifacts:
        citation = DataCitation(
            source_id=artifact_id,
            version=1,
            sha256=hashlib.sha256(raw).hexdigest(),
            locator="document",
            value=filename,
        )
        try:
            extraction = extract_document(raw, filename, media)
            if media == "application/pdf":
                actual = "".join(extraction["text"].split())
                passed = all("".join(line.split()) in actual for line in required_lines)
            elif media == "application/json":
                passed = json.loads(raw) == expected
            elif media == "text/csv":
                actual_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
                expected_rows = [
                    {key: "" if value is None else str(value) for key, value in row.items()}
                    for row in expected["rows"]
                ]
                passed = actual_rows == expected_rows
            else:
                passed = False
            checks.append(
                RequirementAssessment(
                    requirement_id=f"delivery-{artifact_id}",
                    verdict="PASS" if passed else "FAIL",
                    cause="NONE" if passed else "PROVIDER_DEFECT",
                    explanation=(
                        f"Reopened and compared actual {filename} "
                        "with exact accepted sources and report content."
                    ),
                    citations=(citation,),
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            checks.append(
                RequirementAssessment(
                    requirement_id=f"delivery-{artifact_id}",
                    verdict="UNKNOWN",
                    cause="VALIDATOR_FAILURE",
                    explanation=(
                        f"Artifact validator could not establish correctness: {str(exc)[:500]}"
                    ),
                    citations=(citation,),
                )
            )
    return (*source_result, *checks)


def effective_specification(order, now):
    specification = order.snapshot.data_specification
    for amendment in order.data_amendments:
        if amendment.effective_at <= now:
            specification = amendment.specification
    return specification


def evidence_digest(order):
    return digest([reference.model_dump(mode="json") for reference in order.evidence])


def current_data_verification(order, now):
    result = order.data_verification
    specification = effective_specification(order, now)
    if result is None or specification is None or not order.deliveries:
        return False
    required = {r.id for r in specification.requirements}
    required.update(
        f"delivery-{a.evidence_id}"
        for a in (*order.deliveries[-1].artifacts, *order.deliveries[-1].structured_data)
    )
    ids = [check.requirement_id for check in result.checks]
    return (
        result.proposal == order.binding
        and result.specification_sha256 == specification_digest(specification)
        and result.evidence_sha256 == evidence_digest(order)
        and order.snapshot.accepted_at <= result.verified_at <= now
        and set(ids) == required
        and len(ids) == len(set(ids))
        and result.verdict == "PASS"
    )
