"""Greptile P1: dispatch and persisted proposal provenance share one model choice."""

import asyncio

import pytest

from app.contracts.broker import DraftCreate
from app.contracts.improvement import ImprovementCommand
from app.improvement.service import Improvement
from app.storage.jobflow import uid
from tests.broker.conftest import ACTORS
from tests.broker.test_api_and_model import InjectedClient


@pytest.mark.parametrize("legacy", [None, "conflicting-legacy-model"])
@pytest.mark.parametrize("change_during_call", [False, True])
def test_proposal_records_exact_dispatched_model(broker, monkeypatch, legacy, change_during_call):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    if legacy:
        monkeypatch.setenv("ANTHROPIC_MODEL", legacy)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "injected-test-sentinel-not-a-live-key")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    monkeypatch.setenv("APPLICATION_MODEL_BUDGET_PATH", "injected-unused-ledger")
    broker.create_draft(
        ACTORS["customer"],
        DraftCreate(idempotency_key=uid("draft"), intent="recent aggregate data"),
    )

    class Client(InjectedClient):
        async def create(self, **kwargs):
            response = await super().create(**kwargs)
            if change_during_call:
                monkeypatch.setenv("CLAUDE_MODEL", "changed-after-dispatch")
                monkeypatch.setenv("ANTHROPIC_MODEL", "changed-legacy-after-dispatch")
            return response

    client = Client()
    service = Improvement(broker, model_client=client)
    incidents = service.view(
        ACTORS["controller"], "northwind", "aggregate_regional_market_intelligence"
    )["incidents"]
    command = ImprovementCommand(
        idempotency_key=uid("model"),
        verb="propose",
        customer_id="northwind",
        incident_ids=(incidents[0]["id"],),
        mode="ANTHROPIC",
    )
    result = asyncio.run(service.command(ACTORS["controller"], command))
    assert result["status"] == "COMPLETE", result
    assert result["proposer_model"] == client.calls[0]["model"] == "claude-opus-5-5"
    assert (result["input_tokens"], result["output_tokens"]) == (123, 45)
    for identifier in result["patch_ids"]:
        patch = service.record(ACTORS["controller"], identifier)
        assert patch["proposer_model"] == "claude-opus-5-5"
        assert patch["mode"] == "ANTHROPIC_TEST_DOUBLE"
    restarted = Improvement(broker, model_client=client)
    assert asyncio.run(restarted.command(ACTORS["controller"], command)) == result
    assert len(client.calls) == 1
    assert (
        service.view(ACTORS["controller"], "northwind", command.product_id)["active_template"]["id"]
        == "intake-v1"
    )
