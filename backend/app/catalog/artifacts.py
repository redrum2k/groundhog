import hashlib
import io
from functools import lru_cache
from pathlib import Path

import pdfplumber
from pdfminer.psexceptions import PSException
from pdfplumber.utils.exceptions import PdfminerException

from app.contracts.catalog import Artifact, Span
from app.contracts.models import PdfHighlight
from app.orders.service import DomainError


@lru_cache(maxsize=32)
def layout(data: bytes):
    """Cache parsed immutable bytes, never trust cached filesystem contents."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if not 1 <= len(pdf.pages) <= 8:
            raise ValueError("PDF must contain 1-8 pages")
        result = []
        for page in pdf.pages:
            if len(page.chars) > 30000:
                raise ValueError("PDF page exceeds extraction budget")
            result.append(
                (
                    page.extract_text() or "",
                    page.width,
                    page.height,
                    page.extract_text_lines(return_chars=False),
                )
            )
        return tuple(result)


class ArtifactStore:
    """Only content-addressed approved evidence; never exposes arbitrary filesystem tools."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, media_type="application/pdf") -> Artifact:
        if len(data) > 2_000_000:
            raise ValueError("document exceeds 2 MB limit")
        if media_type == "application/pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("upload must be a PDF")
            try:
                layout(data)
            except (PSException, PdfminerException) as exc:
                raise ValueError("PDF is malformed, encrypted or unreadable") from exc
        digest = hashlib.sha256(data).hexdigest()
        extension = {"application/pdf": "pdf", "application/json": "json", "text/csv": "csv"}[
            media_type
        ]
        key = f"objects/{digest}.{extension}"
        path = self.root / key
        path.parent.mkdir(exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("artifact storage collision") from None
        return Artifact(
            artifact_id=digest[:24], sha256=digest, storage_key=key, media_type=media_type
        )

    def read(self, artifact: Artifact) -> bytes:
        path = (self.root / artifact.storage_key).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise DomainError(404, "approved artifact unavailable")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise DomainError(409, "artifact does not match frozen hash")
        return data

    def pages(self, artifact):
        return tuple(page[0] for page in layout(self.read(artifact)))

    def cite(self, artifact, quote: str, page_number=1):
        text, width, height, lines = layout(self.read(artifact))[page_number - 1]
        start = text.find(quote)
        if start < 0:
            raise ValueError("citation text is absent")
        hit = next((line for line in lines if quote in line["text"]), None)
        if not hit:
            raise ValueError("citation has no visible PDF line region")
        return Span(
            artifact_id=artifact.artifact_id,
            sha256=artifact.sha256,
            page=page_number,
            start=start,
            end=start + len(quote),
            quote=quote,
            highlight=PdfHighlight(
                page_number=page_number,
                x0=hit["x0"] / width,
                y0=hit["top"] / height,
                x1=hit["x1"] / width,
                y1=hit["bottom"] / height,
            ),
        )

    def resolve(self, span: Span, artifacts: tuple[Artifact, ...]):
        from app.contracts.dataset import DatasetReference
        from app.datasets import resolve_reference

        if isinstance(span, DatasetReference):
            return resolve_reference(span, artifacts, self)
        artifact = next(
            (a for a in artifacts if a.artifact_id == span.artifact_id and a.sha256 == span.sha256),
            None,
        )
        if artifact is None or artifact.media_type != "application/pdf":
            raise ValueError("citation is outside supplied evidence")
        pages = self.pages(artifact)
        if span.page > len(pages) or pages[span.page - 1][span.start : span.end] != span.quote:
            raise ValueError("citation span does not resolve to stored PDF text")
        if self.cite(artifact, span.quote, span.page) != span:
            raise ValueError("citation highlight does not match stored PDF")
        return span.quote
