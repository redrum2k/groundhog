"""Actionable human-review rows; historical findings remain available in order history."""

from app.contracts.catalog import ReviewRow


def delivery_citations(order, product_id, store):
    if not order.deliveries:
        return ()
    artifact = order.deliveries[-1].pdf
    for page, text in enumerate(store.pages(artifact), 1):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith(f"SELECT {product_id} | "):
                return tuple(
                    store.cite(artifact, value, page) for value in lines[index : index + 3]
                )
            if line.startswith((f"EXCLUDED {product_id} | ", f"UNRESOLVED {product_id} | ")):
                return (store.cite(artifact, line, page),)
    return ()


def review_table(order, store):
    report = order.verification or (
        order.verification_history[-1] if order.verification_history else None
    )
    wording = {r.requirement_id: r.wording for r in order.snapshot.quote.specification.requirements}
    complaint = order.cases[-1].complaint if order.cases else None
    rows = []

    def row(requirement, product, field, assessment, status, *, issue=None):
        delivered = tuple(
            c
            for c in assessment.citations
            if any(c.artifact_id == d.pdf.artifact_id for d in order.deliveries)
        )
        sources = tuple(c for c in assessment.citations if c not in delivered)
        delivered = delivered or delivery_citations(order, product, store)
        return ReviewRow(
            requirement_id=requirement,
            accepted_wording=wording[requirement],
            product=product,
            field=field,
            issue=issue or assessment.explanation,
            source_fact="; ".join(c.quote for c in sources) or "Missing source fact",
            source_citations=sources,
            delivered_value="; ".join(c.quote for c in delivered) or None,
            delivered_citations=delivered,
            result=assessment.result,
            amendment_status=status,
            missing_fact_or_contradiction="; ".join(assessment.missing_facts)
            or assessment.explanation,
            recommended_remedy=assessment.requested_evidence
            or "Review the cited facts and preserve original terms.",
            financial_effect=(
                "No complaint fee. See authorization and ledger; "
                "this row grants no capture authority."
            ),
            required_authority=(
                "Trusted reviewer and established supplier authority; "
                "changed terms require customer/provider consent."
            ),
        )

    if report:
        for obligation, assessment in zip(report.obligations, report.assessments, strict=True):
            relevant = (
                obligation.obligation_id in report.material_blockers
                or obligation.mandatory
                and assessment.result == "FAIL"
                or complaint
                and obligation.subject == complaint.product_id
            )
            if relevant:
                rows.append(
                    row(
                        obligation.requirement_id,
                        obligation.subject,
                        obligation.field,
                        assessment,
                        ", ".join(a.classification for a in order.amendments) or "none",
                        issue=complaint.text if complaint else None,
                    )
                )
    for amendment in order.amendments:
        if amendment.classification == "unresolved" or amendment.applied_revision is None:
            rows.extend(
                row(
                    "R-PROVENANCE",
                    amendment.target_source_id,
                    "amendment_authority",
                    a,
                    amendment.classification,
                )
                for a in amendment.assessment
            )
    for assessment in order.semantic_findings[-1:]:
        if complaint:
            rows.append(
                row(
                    complaint.requirement_id,
                    complaint.product_id,
                    complaint.field,
                    assessment,
                    "see amendment history",
                    issue=complaint.text,
                )
            )
    return tuple(rows)
