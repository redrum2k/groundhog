import base64
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.contracts.catalog import (
    AcceptQuoteCommand,
    ClarifyCommand,
    OrderCommand,
    RequestCommand,
    RevisionCommand,
    UploadCommand,
)
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from corpus.generate import seed  # noqa: E402


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 23, 19, tzinfo=UTC)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def setup(tmp_path):
    clock = Clock()
    service = CatalogService(
        CatalogRepository(tmp_path / "orders.sqlite3"),
        tmp_path / "artifacts",
        clock,
        auto_mock_funding=True,
    )
    return service, clock, seed(service)


def cmd(order, key, cls=OrderCommand, **fields):
    return cls(
        expected_revision=order.revision,
        expected_binding=order.binding,
        idempotency_key=key,
        **fields,
    )


def draft_quote(
    service,
    *,
    key="request",
    prompt="Find storage products under 2 kg and unit price no more than USD 40.",
):
    draft = service.create_request(
        RequestCommand(prompt=prompt, corpus_id="storage-2026", idempotency_key=key)
    )
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"),
    )
    if draft.question:
        draft = service.clarify(
            draft.request_id,
            ClarifyCommand(
                expected_revision=draft.revision,
                idempotency_key="answer",
                question_id=draft.question.question_id,
                text="net unit weight",
            ),
        )
        draft = service.compile_request(
            draft.request_id,
            RevisionCommand(expected_revision=draft.revision, idempotency_key="compile2"),
        )
    quote = service.issue_quote(
        draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="quote")
    )
    return draft, quote


def accepted(service, **kwargs):
    _, quote = draft_quote(service, **kwargs)
    return service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="customer:test", idempotency_key=quote.quote_id
        )
    )


def upload(service, order, artifact, key="upload"):
    return service.upload(
        order.snapshot.order_id,
        cmd(
            order,
            key,
            UploadCommand,
            evidence_request_id=order.evidence_requests[-1].request_id,
            actor="customer:test",
            reason="Readable page for same edition",
            relationship="replacement_page",
            pdf_base64=base64.b64encode(service.store.read(artifact)).decode(),
        ),
    )


def repaired(service, fixtures):
    order = accepted(service)
    order = service.run_one(order.snapshot.order_id)
    order = upload(service, order, fixtures["repair"].artifact)
    order = service.run_one(order.snapshot.order_id)
    return service.run_one(order.snapshot.order_id)
