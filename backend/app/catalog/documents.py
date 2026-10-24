"""Real PDF generation/extraction for the bounded fixture format; no evaluation imports."""

import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.contracts.catalog import ExtractedSource, Product


def pdf_document(title: str, lines: list[str]) -> bytes:
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=letter, invariant=1)
    page.setTitle(title)
    width, height = letter
    number = 0
    chunks = [[]]
    index = 0
    while index < len(lines):
        count = 3 if lines[index].startswith("SELECT ") else 1
        group = lines[index : index + count]
        if len(chunks[-1]) + len(group) > 34:
            chunks.append([])
        chunks[-1].extend(group)
        index += count
    for chunk in chunks:
        number += 1
        page.setFillColor(colors.HexColor("#173B42"))
        page.rect(0, height - 100, width, 100, fill=1, stroke=0)
        page.setFillColor(colors.white)
        page.setFont("Helvetica-Bold", 20)
        page.drawString(38, height - 46, title)
        page.setFont("Helvetica", 9)
        page.drawString(38, height - 68, "CALHACKS / SYNTHETIC CATALOG DEMO / NO LIVE PAYMENTS")
        y = height - 126
        page.setFillColor(colors.HexColor("#173B42"))
        page.setFont("Helvetica", 9)
        for line in chunk:
            if page.stringWidth(line, "Helvetica", 9) > width - 76:
                raise ValueError("PDF line exceeds printable width")
            page.drawString(38, y, line)
            y -= 17
        page.setStrokeColor(colors.HexColor("#CBD5D6"))
        page.line(38, 45, width - 38, 45)
        page.setFont("Helvetica", 8)
        page.drawString(38, 30, "Source citations refer to immutable registered artifacts.")
        page.drawRightString(width - 38, 30, str(number))
        page.showPage()
    page.save()
    return out.getvalue()


def decimal_value(text: str):
    if text == "UNREADABLE":
        return None
    try:
        value = Decimal(text)
        return value if value.is_finite() and value >= 0 else None
    except InvalidOperation:
        return None


def extract_source(source, store) -> ExtractedSource:
    pages = store.pages(source.artifact)
    header_line = next(
        (line for text in pages for line in text.splitlines() if line.startswith("Supplier: ")),
        None,
    )
    if header_line is None:
        raise ValueError("source is missing the bounded catalog identity header")
    match = re.fullmatch(
        r"Supplier: (\S+) / Edition: (\S+) / Effective: (\d{4}-\d{2}-\d{2})", header_line
    )
    if not match:
        raise ValueError("catalog identity header cannot be parsed")
    header_page = next(i + 1 for i, text in enumerate(pages) if header_line in text)
    header = store.cite(source.artifact, header_line, header_page)
    declared = []
    index_citations = []
    products = []
    errors = []
    for page_number, text in enumerate(pages, 1):
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("Records: "):
                declared.extend(line[9:].split(", "))
                index_citations.append(store.cite(source.artifact, line, page_number))
            record = re.fullmatch(r"(S\d+) \| ([a-z_]+) \| (.+)", line)
            if not record:
                continue
            details = lines[i + 1] if i + 1 < len(lines) else ""
            values = re.fullmatch(
                r"net=(\S+) (kg|g) \| shipping=(\S+) (kg|g) \| unit=([A-Z]+) (\S+)", details
            )
            if not values:
                errors.append(f"Required values unreadable for {record[1]}")
                continue
            net, shipping = decimal_value(values[1]), decimal_value(values[3])
            if net is not None and values[2] == "g":
                net /= 1000
            if shipping is not None and values[4] == "g":
                shipping /= 1000
            products.append(
                Product(
                    product_id=record[1],
                    category=record[2],
                    name=record[3],
                    supplier_id=match[1],
                    source_id=source.source_id,
                    net_kg=net,
                    shipping_kg=shipping,
                    currency=values[5],
                    unit_price=decimal_value(values[6]),
                    citations=(
                        store.cite(source.artifact, line, page_number),
                        store.cite(source.artifact, details, page_number),
                    ),
                )
            )
    if not declared:
        errors.append("Declared catalog record index is missing")
    if set(declared) != {p.product_id for p in products}:
        errors.append("Extracted records do not cover the declared catalog index")
    return ExtractedSource(
        source=source,
        edition=match[2],
        effective_date=date.fromisoformat(match[3]),
        declared_ids=tuple(declared),
        products=tuple(products),
        header=header,
        index_citations=tuple(index_citations),
        parse_errors=tuple(errors),
    )


def compare(value, operator, threshold):
    return value < threshold if operator == "lt" else value <= threshold


def disposition(product, terms):
    if product.category != terms.category:
        return "excluded", "category"
    weight = product.net_kg if terms.weight_concept == "net_unit" else product.shipping_kg
    limit = terms.weight_threshold / (1000 if terms.weight_unit == "g" else 1)
    if weight is not None and not compare(weight, terms.weight_operator, limit):
        return "excluded", "weight"
    if (
        product.currency == terms.currency
        and product.unit_price is not None
        and not compare(product.unit_price, terms.price_operator, terms.price_threshold)
    ):
        return "excluded", "price"
    if weight is None or product.unit_price is None or product.currency != terms.currency:
        return "unresolved", "required_value"
    return "included", "qualifies"


def exact_decimal(value, minimum_places):
    """Preserve accepted source precision; padding must never round a fact."""
    places = max(minimum_places, -value.as_tuple().exponent)
    return format(value, f".{places}f")


def output_lines(extracted, terms):
    lines = []
    for source in extracted:
        for product in source.products:
            status, reason = disposition(product, terms)
            if status == "included":
                weight = (
                    product.net_kg if terms.weight_concept == "net_unit" else product.shipping_kg
                )
                lines.extend(
                    [
                        f"SELECT {product.product_id} | {product.name} | {product.supplier_id}",
                        f"{terms.weight_concept}={exact_decimal(weight, 3)} kg | "
                        f"unit={product.currency} {exact_decimal(product.unit_price, 2)}",
                        f"source={source.source.source_id}@{source.source.version} "
                        f"p{product.citations[0].page} sha={source.source.artifact.sha256[:12]}",
                    ]
                )
            else:
                lines.append(f"{status.upper()} {product.product_id} | {reason}")
    return lines


def produce(extracted, terms, store):
    import json

    lines = output_lines(extracted, terms)
    pdf = store.put(pdf_document("Cited product shortlist", lines))
    payload = {
        "derived_from": [s.source.artifact.model_dump(mode="json") for s in extracted],
        "delivery_sha256": pdf.sha256,
        "records": [
            {"product": p.model_dump(mode="json"), "disposition": disposition(p, terms)}
            for source in extracted
            for p in source.products
        ],
    }
    sidecar = store.put(json.dumps(payload, sort_keys=True).encode(), "application/json")
    return pdf, sidecar
