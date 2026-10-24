from types import SimpleNamespace

import pytest

from app.agents.gateway import ClaudeGateway, ModelFailure, OfflineAssessor
from app.contracts.models import Contract, Text


class Response(Contract):
    text: Text


class Client:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.messages = self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_paid_calls_disabled_by_default():
    with pytest.raises(ModelFailure, match="disabled"):
        ClaudeGateway()


def test_documented_messages_parse_validates_structured_output():
    client = Client(SimpleNamespace(stop_reason="end_turn", parsed_output={"text": "assessment"}))
    gateway = ClaudeGateway(enabled=True, model="explicit-test-model", client=client)
    assert gateway.parse(Response, "Assess evidence", {"passage": "untrusted"}).text == "assessment"
    assert client.calls[0]["output_format"] is Response
    assert client.calls[0]["max_tokens"] == 4096 and "tools" not in client.calls[0]
    assert "untrusted" in client.calls[0]["system"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens", "tool_use"])
def test_refusal_and_truncated_output_are_explicit(stop):
    client = Client(SimpleNamespace(stop_reason=stop, parsed_output=None))
    gateway = ClaudeGateway(enabled=True, model="test", client=client)
    with pytest.raises(ModelFailure, match=stop):
        gateway.parse(Response, "Assess", {})


def test_malformed_output_is_not_policy_authority():
    client = Client(
        SimpleNamespace(stop_reason="end_turn", parsed_output={"capture": True, "amount": 1})
    )
    gateway = ClaudeGateway(enabled=True, model="test", client=client)
    with pytest.raises(ModelFailure):
        gateway.parse(Response, "Assess", {})
    with pytest.raises(ModelFailure, match="bounded"):
        gateway.parse(Response, "Assess", {"data": "a" * 50001})


def test_offline_assessor_abstains_without_model_confidence_becoming_fact():
    from app.contracts.catalog import Obligation

    requirement = Obligation(
        obligation_id="authority",
        requirement_id="R-PROVENANCE",
        subject="source",
        field="authority",
        check="authority",
    )
    result = OfflineAssessor().assess_obligation(requirement, "Is the supplier logo authentic?", ())
    assert result.result == "UNKNOWN" and result.provenance.model_score is None


def test_provider_failure_does_not_leave_contract_ready(setup):
    from app.contracts.catalog import RequestCommand, RevisionCommand

    service, _, _ = setup

    class Failure:
        def compile(self, context):
            raise ModelFailure("refusal")

    service.compiler = Failure()
    draft = service.create_request(
        RequestCommand(prompt="storage", corpus_id="storage-2026", idempotency_key="req")
    )
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"),
    )
    assert draft.status == "human_review" and draft.error == "refusal"


def test_compiler_result_after_deadline_is_stale(setup):
    from app.agents.compiler import OfflineCompiler
    from app.contracts.catalog import RequestCommand, RevisionCommand
    from app.orders.service import DomainError

    service, clock, _ = setup

    class SlowCompiler:
        def compile(self, context):
            clock.advance(301)
            return OfflineCompiler().compile(context)

    service.compiler = SlowCompiler()
    draft = service.create_request(
        RequestCommand(
            prompt="storage under 2 kg unit price no more than USD 40",
            corpus_id="storage-2026",
            idempotency_key="request",
        )
    )
    with pytest.raises(DomainError, match="stale"):
        service.compile_request(
            draft.request_id,
            RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"),
        )
    assert service.get_request(draft.request_id).status == "human_review"
