"""Evidence repair classification. Readability and a supplier logo establish no authority."""

from app.catalog.documents import disposition, extract_source
from app.contracts.catalog import Assessment, Provenance

TOOL = Provenance(kind="deterministic", assessor="amendment-checker", version="3.0")


def assess_amendment(amendment, target, registry, store, terms):
    registered = registry.identify(amendment.artifact)
    candidate = registered or target.model_copy(
        update={"artifact": amendment.artifact, "authority": "unverified", "authority_record": None}
    )
    old = extract_source(target, store)
    try:
        new = extract_source(candidate, store)
    except ValueError:
        return (
            "unresolved",
            (
                Assessment(
                    obligation_id=f"amendment/{amendment.amendment_id}",
                    result="UNKNOWN",
                    citations=(old.header,),
                    missing_facts=("Readable supplier identity and catalog values",),
                    reason_code="REQUIRED_VALUE_UNREADABLE",
                    explanation=(
                        "The uploaded document does not establish the requested catalog facts."
                    ),
                    requested_evidence=(
                        "Provide a readable catalog page with its supplier and edition header."
                    ),
                    provenance=TOOL,
                ),
            ),
            None,
        )

    def finding(result, reason, explanation, *, missing=(), conflicts=()):
        return Assessment(
            obligation_id=f"amendment/{amendment.amendment_id}",
            result=result,
            citations=(old.header, new.header),
            missing_facts=missing,
            conflicting_evidence=conflicts,
            reason_code=reason,
            explanation=explanation,
            provenance=TOOL,
            requested_evidence="Provide registered supplier publication or authorized confirmation."
            if result in ("UNKNOWN", "CONFLICT")
            else None,
        )

    if registered is None or candidate.authority == "unverified":
        return (
            "unresolved",
            (
                finding(
                    "UNKNOWN",
                    "SOURCE_AUTHORITY_UNVERIFIED",
                    (
                        "Readable content is not evidence of supplier authority; "
                        "authenticity is unestablished."
                    ),
                    missing=(
                        "Registered publication hash or authorized representative confirmation",
                    ),
                ),
            ),
            None,
        )
    if new.effective_date != candidate.effective_date or new.edition != candidate.edition:
        return (
            "unresolved",
            (
                finding(
                    "CONFLICT",
                    "EFFECTIVE_DATE_CONFLICT",
                    (
                        "Document effective date or edition contradicts its "
                        "registered publication metadata."
                    ),
                    conflicts=(new.header,),
                ),
            ),
            None,
        )
    if new.parse_errors or set(new.declared_ids) != {p.product_id for p in new.products}:
        return (
            "unresolved",
            (
                finding(
                    "UNKNOWN",
                    "REQUIRED_VALUE_UNREADABLE",
                    "Replacement still lacks required readable records.",
                    missing=new.parse_errors or ("Readable records",),
                ),
            ),
            None,
        )
    changed = (
        candidate.source_id != target.source_id
        or candidate.supplier_id != target.supplier_id
        or new.edition != old.edition
        or new.effective_date != old.effective_date
        or set(new.declared_ids) != set(old.declared_ids)
    )
    original = {p.product_id: p for p in old.products}
    for product in new.products:
        before = original.get(product.product_id)
        if before is None:
            changed = True
            continue
        for field in (
            "name",
            "category",
            "supplier_id",
            "net_kg",
            "shipping_kg",
            "unit_price",
            "currency",
        ):
            prior = getattr(before, field)
            if prior is not None and prior != getattr(product, field):
                changed = True
    if changed:
        return (
            "substantive",
            (
                finding(
                    "PASS",
                    "SUBSTANTIVE_CHANGE",
                    (
                        "Verified publication changes agreed facts, edition or "
                        "record scope; explicit new agreement required."
                    ),
                ),
            ),
            candidate,
        )
    if any(disposition(p, terms)[0] == "unresolved" for p in new.products):
        return (
            "unresolved",
            (
                finding(
                    "UNKNOWN",
                    "REQUIRED_VALUE_UNREADABLE",
                    "Required values remain unreadable.",
                    missing=("Readable required numeric values",),
                ),
            ),
            None,
        )
    return (
        "evidence_only",
        (
            finding(
                "PASS",
                "SAME_INFORMATION_RESTORED",
                (
                    "Registered authority, edition, record identity and every "
                    "readable original value agree."
                ),
            ),
        ),
        candidate,
    )
