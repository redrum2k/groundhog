"""Committed catalog projections, separate from the frozen catalog HTTP schema."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from app.contracts.catalog import (
    AcceptQuoteCommand,
    Binding,
    CatalogOrder,
    ClarifyCommand,
    OrderCommand,
    OrderView,
    Quote,
    RequestCommand,
    RequestDraft,
    RevisionCommand,
)
from app.contracts.models import Contract, Digest, Text
from app.contracts.payments import FundingAuthorization, FundingPreparation, PaymentView


class CatalogEvent(Contract):
    event_id: Text
    seq: Annotated[int, Field(ge=1)]
    run_id: Text
    occurred_at: AwareDatetime
    type: Literal["catalog.committed"] = "catalog.committed"
    aggregate_revision: Annotated[int, Field(ge=1)]
    accepted_snapshot_sha256: Digest
    binding: Binding
    actor: Text
    operation: Text
    correlation_id: Text | None = None
    mode: Literal["live_backend"] = "live_backend"
    procedure_version: Text = "catalog-static-v1"
    # These are exact committed domain records, not a story inferred by polling.
    order: CatalogOrder
    payment: PaymentView | None = None


class CatalogEvents(Contract):
    run_id: Text
    events: tuple[CatalogEvent, ...]
    next_cursor: Annotated[int, Field(ge=0)]
    server_time: AwareDatetime
    poll_after_ms: Literal[2000] = 2000


class CatalogRunSummary(Contract):
    run_id: Text
    revision: int
    state: Text
    last_seq: int


class CatalogRunContractExport(Contract):
    event: CatalogEvent
    events: CatalogEvents
    summary: CatalogRunSummary
    request: RequestCommand
    draft: RequestDraft
    revision_command: RevisionCommand
    clarification: ClarifyCommand
    quote: Quote
    acceptance: AcceptQuoteCommand
    order_command: OrderCommand
    order_view: OrderView
    funding_preparation: FundingPreparation
    funding_authorization: FundingAuthorization
