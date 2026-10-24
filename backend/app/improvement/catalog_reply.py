"""Structured interaction contract, explicitly not unrestricted language understanding."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime

from app.contracts.models import Contract, Text


class EvidenceReplyFrame(Contract):
    question_id: Text
    aggregate_revision: int
    target_source_id: Text
    target_version: int
    edition: Text
    recipient: Literal["source_provider", "customer"]
    semantic_kind: Literal["request_evidence", "historical_reference", "hypothetical", "unrelated"]
    slot: Text
    wording: Text
    deadline: AwareDatetime


def current_reply_frame(order):
    request = next((r for r in reversed(order.evidence_requests) if not r.answered), None)
    if request is None:
        return None
    return EvidenceReplyFrame(
        question_id=request.request_id,
        aggregate_revision=order.revision,
        target_source_id=request.target_source.source_id,
        target_version=request.target_source.version,
        edition=request.target_source.edition,
        recipient="source_provider",
        semantic_kind="request_evidence",
        slot="registered_same_edition_readable_page",
        wording=request.prompt,
        deadline=request.deadline,
    )


def reply_is_current(frame, order, now: datetime):
    current = current_reply_frame(order)
    return bool(
        current
        and order.order_state == "waiting_evidence"
        and now < frame.deadline
        and frame.semantic_kind == "request_evidence"
        and frame.recipient == "source_provider"
        and frame.slot == current.slot
        and frame.model_dump(exclude={"wording", "semantic_kind"})
        == current.model_dump(exclude={"wording", "semantic_kind"})
    )
