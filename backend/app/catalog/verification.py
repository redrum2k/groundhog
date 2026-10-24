"""Allowlisted obligations and dependency routing; PDF checks re-extract actual bytes."""

from collections import Counter

from app.catalog.documents import compare, disposition, extract_source, output_lines
from app.contracts.catalog import Assessment, Obligation, Provenance, Verification

TOOL = Provenance(kind="deterministic", assessor="catalog-verifier", version="3.0")


def pdf_records(lines):
    """Bind each product identity to its adjacent values and citation.

    Whole records may reorder, including across pages. Individual lines may not.
    Unknown, incomplete, or duplicated content cannot disappear in normalization.
    """
    records, index = [], 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("SELECT "):
            record = tuple(lines[index : index + 3])
            if (
                len(record) != 3
                or not record[1].startswith(("net_unit=", "shipping="))
                or not record[2].startswith("source=")
            ):
                return None
            records.append(record)
            index += 3
        elif line.startswith(("EXCLUDED ", "UNRESOLVED ")):
            records.append((line,))
            index += 1
        else:
            return None
    return Counter(records)


def material_blockers(obligations, assessments):
    checks = {a.obligation_id: a for a in assessments}
    definitions = {o.obligation_id: o for o in obligations}
    if len(checks) != len(assessments) or set(checks) != set(definitions):
        raise ValueError("every allowlisted obligation must have exactly one assessment")
    seen = set()
    blockers = set()

    def visit(identifier, path):
        if identifier in path:
            raise ValueError("cyclic verification dependencies")
        if identifier in seen:
            return
        seen.add(identifier)
        obligation = definitions[identifier]
        result = checks[identifier]
        if result.result in ("UNKNOWN", "CONFLICT"):
            blockers.add(identifier)
        for dependency in obligation.dependencies:
            if dependency not in definitions:
                raise ValueError("unregistered obligation dependency")
            visit(dependency, {*path, identifier})

    for obligation in obligations:
        if obligation.mandatory and obligation.decision_effect != "none":
            visit(obligation.obligation_id, set())
    return tuple(sorted(blockers))


def verify(context, store, now, *, delivery=None, stage="fulfillment"):
    terms = context.snapshot.quote.specification.terms
    extracted = tuple(extract_source(s, store) for s in context.sources)
    obligations, assessments = [], []

    def add(
        identifier,
        requirement,
        subject,
        field,
        result,
        citations,
        explanation,
        *,
        dependencies=(),
        mandatory=False,
        reason="CHECKED",
        missing=(),
        conflicts=(),
        request=None,
    ):
        obligations.append(
            Obligation(
                obligation_id=identifier,
                requirement_id=requirement,
                subject=subject,
                field=field,
                check=identifier.split(":")[-1],
                dependencies=dependencies,
                mandatory=mandatory,
            )
        )
        assessments.append(
            Assessment(
                obligation_id=identifier,
                result=result,
                citations=tuple(citations),
                missing_facts=missing,
                conflicting_evidence=conflicts,
                reason_code=reason,
                explanation=explanation,
                requested_evidence=request,
                provenance=TOOL,
            )
        )

    eligible_ids = []
    headers = tuple(s.header for s in extracted)
    for source in extracted:
        key = source.source.source_id
        trusted = source.source.authority in terms.source_policy.accepted_authority
        if any(p.supplier_id != source.source.supplier_id for p in source.products):
            trusted = False
        add(
            f"{key}:authority",
            "R-PROVENANCE",
            key,
            "authority",
            "PASS" if trusted else "UNKNOWN",
            (source.header,),
            "Registry authority is established."
            if trusted
            else "Authority is not established; this does not prove forgery.",
            reason="CHECKED" if trusted else "SOURCE_AUTHORITY_UNVERIFIED",
            missing=()
            if trusted
            else ("Registered publication or authorized supplier confirmation",),
            request=None
            if trusted
            else "Provide a registered supplier publication or authorized supplier confirmation.",
        )
        effective = (
            source.effective_date == source.source.effective_date
            and source.edition == source.source.edition
        )
        add(
            f"{key}:date",
            "R-PROVENANCE",
            key,
            "effective_date",
            "PASS" if effective else "CONFLICT",
            (source.header,),
            "Compare actual edition/effective date with the frozen registry.",
            reason="CHECKED" if effective else "EFFECTIVE_DATE_CONFLICT",
            conflicts=() if effective else (source.header,),
            request=None
            if effective
            else "Provide an authorized confirmation of the applicable edition and effective date.",
        )
        add(
            f"{key}:index",
            "R-COMPLETENESS",
            key,
            "record_index",
            "UNKNOWN" if source.parse_errors else "PASS",
            source.index_citations or (source.header,),
            "; ".join(source.parse_errors)
            if source.parse_errors
            else "Declared record index is fully extracted.",
            mandatory=True,
            missing=source.parse_errors,
            reason="REQUIRED_VALUE_UNREADABLE" if source.parse_errors else "CHECKED",
            request="Provide readable pages from the same catalog edition."
            if source.parse_errors
            else None,
        )
        for product in source.products:
            pid = f"{key}/{product.product_id}"
            add(
                f"{pid}:category",
                "R-CATEGORY",
                product.product_id,
                "category",
                "PASS" if product.category == terms.category else "FAIL",
                product.citations,
                f"Recorded category: {product.category}; accepted category: {terms.category}.",
            )
            weight = product.net_kg if terms.weight_concept == "net_unit" else product.shipping_kg
            threshold = terms.weight_threshold / (1000 if terms.weight_unit == "g" else 1)
            for field, value, operator, limit in (
                ("weight", weight, terms.weight_operator, threshold),
                (
                    "price",
                    product.unit_price if product.currency == terms.currency else None,
                    terms.price_operator,
                    terms.price_threshold,
                ),
            ):
                result = (
                    "UNKNOWN"
                    if value is None
                    else "PASS"
                    if compare(value, operator, limit)
                    else "FAIL"
                )
                add(
                    f"{pid}:{field}",
                    f"R-{field.upper()}",
                    product.product_id,
                    field,
                    result,
                    product.citations,
                    f"{field}: {value}; operator {operator}; limit {limit}.",
                    missing=(f"Readable {field} with the agreed concept and currency",)
                    if value is None
                    else (),
                    reason="REQUIRED_VALUE_UNREADABLE" if value is None else "CHECKED",
                    request=(
                        f"Provide a readable page for {product.product_id} "
                        f"from edition {source.edition}."
                    )
                    if value is None
                    else None,
                )
            status, reason = disposition(product, terms)
            deps = [f"{key}:authority", f"{key}:date", f"{pid}:category"]
            if status == "excluded":
                if reason in ("weight", "price"):
                    deps.append(f"{pid}:{reason}")
            else:
                deps.extend((f"{pid}:weight", f"{pid}:price"))
            identifier = f"{pid}:eligibility"
            eligible_ids.append(identifier)
            add(
                identifier,
                "R-COMPLETENESS",
                product.product_id,
                "eligibility",
                "UNKNOWN" if status == "unresolved" else "PASS",
                product.citations,
                f"{status}: {reason}",
                dependencies=tuple(deps),
                missing=("Eligibility depends on missing required values",)
                if status == "unresolved"
                else (),
                reason="REQUIRED_VALUE_UNREADABLE" if status == "unresolved" else "CHECKED",
            )
    ids = [p.product_id for s in extracted for p in s.products]
    unique = len(ids) == len(set(ids))
    add(
        "global:fields",
        "R-FIELDS",
        "all_products",
        "identity",
        "PASS" if unique else "FAIL",
        headers,
        "Unique product identity and required extracted fields.",
        mandatory=True,
    )
    add(
        "global:completeness",
        "R-COMPLETENESS",
        "all_products",
        "completeness",
        "PASS",
        headers,
        "Every declared product is included, excluded with a reason, or explicitly unresolved.",
        dependencies=tuple(eligible_ids),
        mandatory=True,
    )
    add(
        "global:provenance",
        "R-PROVENANCE",
        "all_sources",
        "provenance",
        "PASS",
        headers,
        "Exact source hashes and resolved citation spans retained.",
        dependencies=tuple(
            f"{s.source.source_id}:{kind}" for s in extracted for kind in ("authority", "date")
        ),
        mandatory=True,
    )
    if delivery:
        expected = output_lines(extracted, terms)
        # Compare independently regenerated canonical records with actual PDF text, not sidecar.
        boilerplate = {
            "Cited product shortlist",
            "CALHACKS / SYNTHETIC CATALOG DEMO / NO LIVE PAYMENTS",
        }
        meaningful = []
        for page, text in enumerate(store.pages(delivery), 1):
            footer = f"Source citations refer to immutable registered artifacts. {page}"
            meaningful.extend(
                line for line in text.splitlines() if line not in boilerplate and line != footer
            )
        actual_records = pdf_records(meaningful)
        correct = actual_records is not None and actual_records == pdf_records(expected)
        citation = store.cite(delivery, "Cited product shortlist")
        add(
            "global:pdf",
            "R-PDF",
            "delivery",
            "pdf",
            "PASS" if correct else "FAIL",
            (citation,),
            (
                "Actual PDF records, amounts, exclusions and citations "
                "compared to source-derived records."
            ),
            mandatory=True,
        )
    blockers = material_blockers(obligations, assessments)
    failures = any(
        a.result == "FAIL" and o.mandatory for o, a in zip(obligations, assessments, strict=True)
    )
    report = Verification(
        binding=context.binding,
        stage=stage,
        obligations=tuple(obligations),
        assessments=tuple(assessments),
        material_blockers=blockers,
        provider_defect=bool(delivery and failures),
        passed=not blockers and not failures,
        created_at=now,
    )
    return report, extracted
