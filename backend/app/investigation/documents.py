"""Bounded extraction with original-byte identity and reproducible text locations."""

import csv
import hashlib
import io
import json
import re
from pathlib import PurePath

import pdfplumber

from app.contracts.jobflow import Evidence, SourceLocation

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 100_000
MAX_PAGES = 20


class DocumentError(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DocumentError("Duplicate JSON keys are ambiguous")
        result[key] = value
    return result


def extract_document(raw: bytes, filename: str, media_type: str) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise DocumentError("Document must contain between 1 byte and 2 MiB")
    if not filename or len(filename) > 160 or any(c in filename for c in "/\\:\x00"):
        raise DocumentError("A simple filename is required")
    allowed = {
        "text/plain": {".txt"},
        "application/pdf": {".pdf"},
        "application/json": {".json"},
        "text/csv": {".csv"},
    }
    if PurePath(filename).suffix.lower() not in allowed.get(media_type, set()):
        raise DocumentError("Filename and supported media type must agree")
    pages = []
    structured = None
    try:
        if media_type == "application/pdf":
            if not raw.startswith(b"%PDF-"):
                raise DocumentError("Invalid PDF signature")
            with pdfplumber.open(io.BytesIO(raw), unicode_norm="NFC") as pdf:
                if not 0 < len(pdf.pages) <= MAX_PAGES:
                    raise DocumentError("PDF page limit is 20")
                for number, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    words = page.extract_words()
                    if len(words) > 20_000:
                        raise DocumentError("PDF page text is too large")
                    pages.append(
                        {
                            "page": number,
                            "text": text,
                            "words": [
                                {
                                    "text": w["text"],
                                    "rectangle": [
                                        w["x0"] / page.width,
                                        w["top"] / page.height,
                                        w["x1"] / page.width,
                                        w["bottom"] / page.height,
                                    ],
                                }
                                for w in words
                            ],
                        }
                    )
                    if sum(len(p["text"]) for p in pages) > MAX_TEXT:
                        raise DocumentError("Extracted text limit exceeded")
            text = "\n".join(p["text"] for p in pages)
        else:
            text = raw.decode("utf-8-sig", errors="strict")
            if media_type == "application/json":
                structured = json.loads(text, object_pairs_hook=_unique_object)
            elif media_type == "text/csv":
                rows = list(csv.reader(io.StringIO(text), strict=True))
                if not rows or len(rows) > 1001 or len(rows[0]) > 100:
                    raise DocumentError("CSV requires a header and at most 1000 data rows")
                if len(set(rows[0])) != len(rows[0]) or any(not c for c in rows[0]):
                    raise DocumentError("CSV columns must be named and unique")
                if any(len(row) != len(rows[0]) for row in rows[1:]):
                    raise DocumentError("CSV rows must match the header")
                structured = {"columns": rows[0], "rows": rows[1:]}
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("Document could not be safely extracted") from exc
    if not text.strip() or len(text) > MAX_TEXT:
        raise DocumentError("Readable bounded text is required; scanned PDFs require review")
    return {
        "text": text,
        "pages": pages,
        "structured": structured,
        "media_type": media_type,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def cite(source: Evidence, quote: str) -> SourceLocation:
    start = source.text.find(quote)
    if not quote or start < 0:
        raise DocumentError("Citation must quote supplied source text exactly")
    return SourceLocation(
        source_id=source.id,
        version=source.version,
        sha256=source.sha256,
        quote=quote,
        locator=f"text:{start}:{start + len(quote)}",
    )


def validate_citation(sources: list[Evidence], citation: SourceLocation) -> None:
    source = next((s for s in sources if s.id == citation.source_id), None)
    if source is None or (source.version, source.sha256) != (citation.version, citation.sha256):
        raise DocumentError("Citation names an unavailable source version")
    match = re.fullmatch(r"text:(\d+):(\d+)", citation.locator)
    if match is None:
        raise DocumentError("A precise text range is required")
    start, end = map(int, match.groups())
    if not 0 <= start < end <= len(source.text) or source.text[start:end] != citation.quote:
        raise DocumentError("Citation quote does not match the exact range")
