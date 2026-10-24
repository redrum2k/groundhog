"""Invoice register bytes and structured sidecar, using the existing artifact store."""

import io
import json
from collections import defaultdict
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.investigation.documents import extract_document
from app.provider.jobflow import source_values, store_evidence, verify
from app.runtime.jobflow_policy import effective_fields
from app.storage.jobflow import DomainError, canonical


def register_data(store, db, order, now):
    groups = defaultdict(list)
    for job in order.jobs:
        if job.kind != "ORIGINAL":
            continue
        raw, meta, _ = store.artifact(db, order.id, job.source_id)
        output, _, _ = store.artifact(db, order.id, job.artifact_id)
        if job.processing != "VALIDATED" or any(
            check.state != "PASSED" for check in verify(raw, output, job.source_id, job.fields)
        ):
            raise DomainError("A register cannot publish while an original extraction has failed")
        values = source_values(raw)
        fields = set(job.fields)
        for child in order.jobs:
            if (
                child.parent_id == job.id
                and child.kind == "DISPUTED_FIELD"
                and child.processing == "VALIDATED"
            ):
                child_raw, _, _ = store.artifact(db, order.id, child.artifact_id)
                if any(
                    check.state != "PASSED"
                    for check in verify(raw, child_raw, job.source_id, child.fields)
                ):
                    raise DomainError("Field regeneration is not source-validated")
                fields.update(child.fields)
        if not set(effective_fields(order, now)) <= fields:
            raise DomainError("Effective scope requires field delivery for every original unit")
        required = tuple(
            sorted(
                {
                    "invoice_number",
                    "vendor",
                    "invoice_date",
                    "currency",
                    "amount",
                    *effective_fields(order, now),
                }
            )
        )
        if any(not values.get(field) for field in required):
            raise DomainError("Missing register source field; require source review")
        groups[values["invoice_number"]].append((values, meta["filename"], job.source_id))
    rows, exceptions = [], []
    totals = defaultdict(Decimal)
    vendors = defaultdict(Decimal)
    for identifier, sources in sorted(groups.items()):
        variants = {canonical({k: values[k] for k in required}) for values, _, _ in sources}
        refs = [{"filename": name, "source_id": sid, "page": 1} for _, name, sid in sources]
        if len(variants) != 1:
            exceptions.append(
                {
                    "invoice_number": identifier,
                    "reason": "Conflicting source versions",
                    "sources": refs,
                }
            )
            continue
        values = sources[0][0]
        amount = Decimal(values["amount"])
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise DomainError("Unsupported invoice amount precision")
        row = {field: values[field] for field in required}
        row["sources"] = refs
        rows.append(row)
        totals[values["currency"]] += amount
        vendors[(values["currency"], values["vendor"])] += amount
    return {
        "rows": rows,
        "exceptions": exceptions,
        "totals": {currency: f"{value:.2f}" for currency, value in sorted(totals.items())},
        "vendor_totals": [
            {"currency": currency, "vendor": vendor, "amount": f"{value:.2f}"}
            for (currency, vendor), value in sorted(vendors.items())
        ],
        "scope": "Invoice register only. No FX conversion, payment-status or category inference.",
    }


def register_lines(data):
    lines = ["INVOICE REGISTER", "Synthetic evidence - mock workflow", data["scope"]]
    for row in data["rows"]:
        lines.append(
            f"{row['invoice_number']} | {row['vendor']} | {row['invoice_date']} | "
            f"{row['currency']} {row['amount']}"
        )
        lines.extend(f"Source: {ref['filename']} page {ref['page']}" for ref in row["sources"])
        for field, value in row.items():
            if field not in {
                "invoice_number",
                "vendor",
                "invoice_date",
                "currency",
                "amount",
                "sources",
            }:
                lines.append(f"{field}: {value}")
    lines.append("EXCEPTIONS")
    if not data["exceptions"]:
        lines.append("None")
    for item in data["exceptions"]:
        lines.append(f"{item['invoice_number']}: {item['reason']}")
        lines.extend(f"Source: {ref['filename']} page {ref['page']}" for ref in item["sources"])
    lines.append("VENDOR SUBTOTALS")
    lines.extend(
        f"{row['vendor']}: {row['currency']} {row['amount']}" for row in data["vendor_totals"]
    )
    lines.extend(f"TOTAL {currency} {amount}" for currency, amount in data["totals"].items())
    return lines


def publish_register(store, db, order, now):
    data = register_data(store, db, order, now)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter, invariant=1)
    pdf.setTitle("Invoice register and exceptions")
    y, page = 740, 1
    for line in register_lines(data):
        if (
            y < 64
            or (line.startswith("INV-") and y < 84)
            or (line in {"EXCEPTIONS", "VENDOR SUBTOTALS"} and y < 104)
        ):
            pdf.setFont("Helvetica", 8)
            pdf.drawRightString(558, 36, f"Page {page}")
            pdf.showPage()
            page += 1
            y = 740
        pdf.setFillColor(colors.HexColor("#163a30"))
        pdf.setFont(
            "Helvetica-Bold"
            if line in {"INVOICE REGISTER", "EXCEPTIONS", "VENDOR SUBTOTALS"}
            else "Helvetica",
            9,
        )
        if pdf.stringWidth(line) > 504:
            raise DomainError("Register line exceeds the supported page width")
        pdf.drawString(54, y, line)
        y -= 20
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(558, 36, f"Page {page}")
    pdf.save()
    raw = output.getvalue()
    document = store_evidence(
        db,
        order,
        raw,
        filename="invoice-register.pdf",
        media_type="application/pdf",
        kind="artifact",
        authority="COMPANY_RECORD",
        actor_id="register-provider",
        now=now,
        derived_from=[job.source_id for job in order.jobs if job.kind == "ORIGINAL"],
        extraction=extract_document(raw, "invoice-register.pdf", "application/pdf"),
    )
    sidecar = store_evidence(
        db,
        order,
        canonical(data).encode(),
        filename="invoice-register.json",
        media_type="application/json",
        kind="artifact",
        authority="COMPANY_RECORD",
        actor_id="register-provider",
        now=now,
        derived_from=[document.id],
    )
    return document, sidecar


def verify_register(store, db, order, record, now):
    delivery = record.deliveries[-1]
    document = next(item for item in delivery.artifacts if item.media_type == "application/pdf")
    raw, _, _ = store.artifact(db, order.id, document.evidence_id)
    parsed = extract_document(raw, "invoice-register.pdf", "application/pdf")
    sidecar_raw, _, _ = store.artifact(db, order.id, delivery.structured_data[0].evidence_id)
    expected = register_data(store, db, order, now)
    if json.loads(sidecar_raw) != expected:
        raise DomainError("Register sidecar differs from independently reopened source invoices")
    expected_lines = register_lines(expected)
    actual_lines = [line for line in parsed["text"].splitlines() if not line.startswith("Page ")]
    if actual_lines != expected_lines:
        raise DomainError("Actual delivered PDF differs from independently verified register")
    return parsed
