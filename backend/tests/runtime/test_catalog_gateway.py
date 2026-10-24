from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.agents.gateway import ClaudeGateway, ModelFailure
from tests.investigation.test_gateway import Client, Response


def test_default_sdk_configuration_and_each_request_are_bounded(monkeypatch, tmp_path):
    from app.agents.budget import ModelBudget
    from tests.investigation.test_model_budget import budget

    ledger = budget(tmp_path)
    monkeypatch.setattr(ModelBudget, "configured", lambda: ledger)
    client = Client(
        SimpleNamespace(
            stop_reason="end_turn",
            parsed_output={"text": "valid"},
            usage={"input_tokens": 1, "output_tokens": 1},
        )
    )
    settings = []

    def sdk(**kwargs):
        settings.append(kwargs)
        return client

    monkeypatch.setattr(anthropic, "Anthropic", sdk)
    gateway = ClaudeGateway(enabled=True, model="claude-opus-5-5")
    assert gateway.parse(Response, "Assess", {}).text == "valid"
    assert settings == [
        {"base_url": "https://api.anthropic.com", "timeout": 20.0, "max_retries": 0}
    ]
    assert ledger.summary()["requests_used"] == 1
    assert client.calls[0]["timeout"] == 20.0
    assert client.calls[0]["max_tokens"] == 4096 and "tools" not in client.calls[0]


def test_input_budget_includes_instructions_and_never_calls_transport():
    client = Client(None)
    gateway = ClaudeGateway(enabled=True, model="offline-test", client=client)
    with pytest.raises(ModelFailure, match="bounded"):
        gateway.parse(Response, "x" * 200, {"text": "a" * 49900})
    assert not client.calls


def test_transport_and_stop_errors_are_redacted(caplog):
    caplog.set_level("INFO", logger="app.agents.gateway")

    class Failure:
        messages = None

        def __init__(self):
            self.messages = self

        def parse(self, **kwargs):
            raise anthropic.APIConnectionError(
                message="private document and secret credential",
                request=httpx.Request("POST", "https://example.invalid/secret"),
            )

    gateway = ClaudeGateway(enabled=True, model="offline-test", client=Failure())
    with pytest.raises(ModelFailure) as error:
        gateway.parse(Response, "Assess", {"text": "private document"})
    assert str(error.value) == "Claude failure: APIConnectionError"
    gateway.client = Client(SimpleNamespace(stop_reason="secret", parsed_output=None))
    with pytest.raises(ModelFailure, match="incomplete"):
        gateway.parse(Response, "Assess", {})
    assert "secret" not in caplog.text and "private document" not in caplog.text
    assert "model stage=Response" in caplog.text and "outcome=failed" in caplog.text
