"""Additive broker API; identities and base settlement remain owned by jobflow."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt

from app.contracts.api import OrderView as BaseOrderView
from app.contracts.data_product import DataSpecification, Frozen, Name, Parameters, SourcePin
from app.contracts.jobflow import Model
from app.contracts.models import Money, ProposalBinding


class IntentMessage(Frozen):
    id: Name
    actor_id: Name
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    created_at: AwareDatetime
    field: str | None = None


class DraftQuestion(Frozen):
    id: Name
    field: Name
    prompt: Annotated[str, Field(min_length=1, max_length=600)]
    answer_id: str | None = None


class IntakeDraft(Model):
    id: Name
    customer_id: Name
    revision: Annotated[StrictInt, Field(ge=1)] = 1
    product_id: Name = "aggregate_regional_market_intelligence"
    template_version: Name = "intake-v1"
    validator_bindings: dict[str, str] = Field(default_factory=dict)
    template_approved_by: str | None = None
    messages: list[IntentMessage]
    parameters: Parameters = Field(default_factory=Parameters)
    sources: list[SourcePin] = Field(default_factory=list)
    questions: list[DraftQuestion] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    provider_capability: Literal["UNREVIEWED", "SUPPORTED", "UNSUPPORTED"] = "UNREVIEWED"
    provider_reason: str | None = None
    offered_price: Money | None = None
    specification: DataSpecification | None = None
    acceptance_digest: str | None = None
    provider_accepted_digest: str | None = None
    provider_actor_id: str | None = None
    customer_accepted_digest: str | None = None
    order_id: str | None = None
    parent_order_id: str | None = None
    human_tasks: list["HumanTask"] = Field(default_factory=list)
    status: Literal["DRAFT", "CLARIFYING", "READY", "ACCEPTED", "UNSUPPORTED", "DECLINED"] = "DRAFT"
    created_at: AwareDatetime


class BrokerQuestion(Model):
    id: Name
    issue_id: Name
    text: Annotated[str, Field(min_length=1, max_length=600)]
    recipient: Literal["customer", "provider", "controller"]
    requirement_id: Name
    binding: ProposalBinding
    specification_sha256: str
    status: Literal["OPEN", "ANSWERED", "CANCELLED"] = "OPEN"
    answer_id: str | None = None


class HumanTask(Model):
    id: Name
    issue_id: Name
    owner: Literal["controller"] = "controller"
    state: Literal["OPEN", "RESOLVED"] = "OPEN"
    reason: str
    missing_facts: list[str]
    evidence: list[SourcePin]
    binding: ProposalBinding | None
    next_action: str = (
        "Supply authenticated evidence or obtain a mutually accepted clarification, then resume."
    )
    decision: str | None = None
    decided_by: str | None = None
    created_at: AwareDatetime
    resolved_at: AwareDatetime | None = None


IntakeDraft.model_rebuild()


class BrokerAmendment(Model):
    id: Name
    specification: DataSpecification
    effective_at: AwareDatetime
    digest: str
    customer_accepted_by: str | None = None
    provider_accepted_by: str | None = None


class BrokerRecord(Model):
    id: Name
    draft_id: Name
    customer_id: Name
    revision: Annotated[StrictInt, Field(ge=1)] = 1
    original_specification: DataSpecification
    amendments: list[BrokerAmendment] = Field(default_factory=list)
    questions: list[BrokerQuestion] = Field(default_factory=list)
    messages: list[IntentMessage] = Field(default_factory=list)
    human_tasks: list[HumanTask] = Field(default_factory=list)
    source_artifact_ids: list[str]
    delivery_artifact_ids: list[str] = Field(default_factory=list)
    issue_id: str | None = None
    question_count: Annotated[StrictInt, Field(ge=0, le=2)] = 0
    overall_case_deadline: AwareDatetime
    resolution: Literal["NO_REMEDY", "CORRECTED", "HUMAN_REVIEW"] | None = None
    parent_order_id: str | None = None
    base_order: BaseOrderView | None = None
    colour: Literal["green", "red", "orange"] = "orange"
    owner: str = "provider"
    next_action: str = "Produce the accepted data product"


class DraftCreate(Frozen):
    idempotency_key: Name
    intent: Annotated[str, Field(min_length=1, max_length=8000)]
    product_id: Name = "aggregate_regional_market_intelligence"
    parent_order_id: str | None = None


class BrokerCommand(Frozen):
    idempotency_key: Name
    expected_revision: Annotated[StrictInt, Field(ge=1)]
    verb: Literal[
        "clarify_intake",
        "answer_intake",
        "offer",
        "accept_specification",
        "decline",
        "produce",
        "accept_delivery",
        "dispute",
        "investigate",
        "answer",
        "resolve_human",
        "propose_amendment",
        "accept_amendment",
    ]
    question_id: str | None = None
    field: str | None = None
    text: Annotated[str | None, Field(max_length=8000)] = None
    value: str | int | list[str] | None = None
    price: Money | None = None
    digest: str | None = None
    capability: Literal["SUPPORTED", "UNSUPPORTED"] | None = None
    authorization_expires_at: AwareDatetime | None = None
    task_id: str | None = None
    decision: Literal["RESUME", "RETAIN_HOLD"] | None = None
    specification: DataSpecification | None = None
    effective_at: AwareDatetime | None = None
    amendment_id: str | None = None


class SourceUpload(Frozen):
    idempotency_key: Name
    expected_revision: Annotated[StrictInt, Field(ge=1)]
    filename: Annotated[str, Field(min_length=1, max_length=160)]
    content_base64: Annotated[str, Field(min_length=1, max_length=2_800_000)]


class BrokerContractExport(Frozen):
    draft: IntakeDraft
    order: BrokerRecord
    command: BrokerCommand
    draft_create: DraftCreate
    source_upload: SourceUpload
