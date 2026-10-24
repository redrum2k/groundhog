import hashlib
import io

import pytest
from reportlab.pdfgen.canvas import Canvas

from app.investigation.documents import DocumentError, extract_document


def invoice_pdf(text=True):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792), invariant=1)
    if text:
        canvas.setFont("Helvetica", 14)
        canvas.drawString(54, 738, "Northwind invoice N-001")
        canvas.setFont("Helvetica", 11)
        canvas.drawString(54, 702, "Amount: USD 1200.00")
        canvas.drawString(54, 681, "Due date: 2026-11-01")
    else:
        canvas.rect(54, 650, 200, 80)
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


def test_actual_pdf_extracts_original_bytes_and_normalized_word_locations():
    raw = invoice_pdf()
    extracted = extract_document(raw, "invoice.pdf", "application/pdf")
    assert "1200.00" in extracted["text"]
    assert extracted["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(extracted["pages"]) == 1
    for word in extracted["pages"][0]["words"]:
        x0, y0, x1, y1 = word["rectangle"]
        assert 0 <= x0 < x1 <= 1
        assert 0 <= y0 < y1 <= 1


def test_pdf_without_readable_text_needs_review():
    with pytest.raises(DocumentError, match="Readable bounded text"):
        extract_document(invoice_pdf(text=False), "scan.pdf", "application/pdf")
