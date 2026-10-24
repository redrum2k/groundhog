"""Controlled synthetic PDF source and extraction adapter; no external calls."""

import hashlib
import io
import json

import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.contracts.jobflow import Check, Evidence
from app.investigation.documents import cite as exact_cite
from app.storage.jobflow import DomainError, canonical, uid

BASE_FIELDS = ["invoice_number", "vendor", "amount", "currency"]
ADDED_FIELDS = ["purchase_order", "cost_center", "tax_id", "payment_terms"]
ALL_FIELDS = BASE_FIELDS + ["invoice_date", "due_date"] + ADDED_FIELDS


def validate_fields(fields, *, allow_empty=False):
    if (not fields and not allow_empty) or len(fields) != len(set(fields)):
        raise DomainError("Fields must be a nonempty unique list", 422)
    if set(fields) - set(ALL_FIELDS):
        raise DomainError("Unsupported extraction field", 422)


def invoice(index, overrides=None):
    values = {
        "invoice_number": f"INV-{index:04d}",
        "vendor": f"Synthetic Vendor {index % 7 + 1}",
        "amount": f"{100 + index}.25",
        "currency": "USD",
        "invoice_date": "2026-10-01",
        "due_date": "2026-11-30",
        "purchase_order": f"PO-{index:04d}",
        "cost_center": "OPS-100",
        "tax_id": "SIM-TAX-001",
        "payment_terms": "Net 30",
    }
    if overrides:
        validate_fields(list(overrides))
        values.update(overrides)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter, invariant=1)
    pdf.setTitle(f"Synthetic invoice {index}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(54, 738, "SYNTHETIC INVOICE")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(54, 715, "Fictional business record - local demonstration only")
    pdf.line(54, 700, 558, 700)
    for row, (key, value) in enumerate(values.items()):
        pdf.setFont("Helvetica", 12)
        pdf.drawString(54, 666 - 32 * row, f"{key}: {value}")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        54, 54, "USD amounts describe source invoices, not jobflow service charges.  |  1 / 1"
    )
    pdf.save()
    return buffer.getvalue()


def parse_pdf(raw):
    with pdfplumber.open(io.BytesIO(raw)) as document:
        if len(document.pages) != 1:
            raise DomainError("Synthetic source must contain one page")
        page = document.pages[0]
        text = page.extract_text() or ""
        words = page.extract_words()
        return {
            "text": text,
            "pages": [
                {
                    "page": 1,
                    "text": text,
                    "width": page.width,
                    "height": page.height,
                    "words": words,
                }
            ],
        }


def source_values(raw):
    text = parse_pdf(raw)["text"]
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(": ")
        if separator and key in ALL_FIELDS:
            if key in values:
                raise DomainError("Ambiguous duplicate invoice field")
            values[key] = value
    return values


def extract(raw, source_id, fields):
    validate_fields(fields)
    values = source_values(raw)
    return canonical(
        {
            "source_id": source_id,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "fields": {field: values.get(field) for field in fields},
        }
    ).encode()


def verify(source_raw, output_raw, source_id, fields):
    """Reopen both byte streams independently of the producer's success status."""
    values = source_values(source_raw)
    try:
        output = json.loads(output_raw)
        if not isinstance(output, dict) or not isinstance(output.get("fields"), dict):
            raise ValueError("Output must contain a fields object")
        lineage = (
            output["source_id"] == source_id
            and output["source_sha256"] == hashlib.sha256(source_raw).hexdigest()
        )
        checks = [
            Check(
                id=uid("check"),
                label=field,
                state="PASSED"
                if lineage
                and values.get(field) is not None
                and output["fields"].get(field) == values[field]
                else "FAILED",
                detail=f"Compared {field} with exact source PDF bytes",
            )
            for field in fields
        ]
    except (ValueError, KeyError, TypeError):
        checks = [
            Check(
                id=uid("check"),
                label="artifact",
                state="FAILED",
                detail="Malformed output or missing source lineage",
            )
        ]
    return checks


def store_evidence(
    db,
    order,
    raw,
    *,
    filename,
    media_type,
    kind,
    authority,
    actor_id,
    now,
    derived_from=None,
    source_id=None,
    extraction=None,
    version=1,
):
    if extraction is None:
        extraction = parse_pdf(raw) if media_type == "application/pdf" else {"text": raw.decode()}
    evidence = Evidence(
        id=source_id or uid("source"),
        version=version,
        sha256=hashlib.sha256(raw).hexdigest(),
        filename=filename,
        media_type=media_type,
        kind=kind,
        authority=authority,
        text=extraction["text"],
        created_at=now,
        origin_actor_id=actor_id,
        derived_from=derived_from or [],
    )
    db.execute(
        "INSERT INTO jf_artifacts VALUES(?,?,?,?,?)",
        (
            evidence.id,
            order.id,
            evidence.model_dump_json(),
            raw,
            canonical(extraction),
        ),
    )
    order.evidence.append(evidence)
    return evidence


def cite(evidence, quote=None):
    return exact_cite(evidence, quote or evidence.text)


def cite_pdf_field(evidence, parsed, field):
    page = parsed["pages"][0]
    label = next((word for word in page["words"] if word["text"] == f"{field}:"), None)
    line = next(
        (line for line in evidence.text.splitlines() if line.startswith(f"{field}: ")), None
    )
    if label is None or line is None:
        return cite(evidence)
    words = [word for word in page["words"] if abs(word["top"] - label["top"]) < 1]
    citation = cite(evidence, line)
    citation.page = page["page"]
    citation.rectangle = (
        min(word["x0"] for word in words) / page["width"],
        min(word["top"] for word in words) / page["height"],
        max(word["x1"] for word in words) / page["width"],
        max(word["bottom"] for word in words) / page["height"],
    )
    return citation
