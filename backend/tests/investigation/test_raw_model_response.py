import anthropic
import httpx
import pytest
from pydantic import BaseModel

from app.agents.bounded_client import BoundedClient
from tests.investigation.test_model_budget import budget


def test_original_response_saved_and_costed_before_schema_failure(tmp_path):
    saved = []
    usage = {"input_tokens": 25, "output_tokens": 10}
    body = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "usage": usage,
        "content": [{"type": "text", "text": "malformed"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
    }

    class Output(BaseModel):
        ok: bool

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=body)

    transport = anthropic.Anthropic(
        api_key="synthetic-test-sentinel",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    ledger = budget(tmp_path)
    client = BoundedClient(client=transport, budget=ledger)
    client.response_sink = saved.append
    with pytest.raises(ValueError):
        client.parse(model="claude-opus-5-5", max_tokens=100, messages=[], output_format=Output)
    assert saved == [body] and len(calls) == 1
    assert client.last_response == body
    assert ledger.summary()["known_cost_usd"] == 0.0003
    assert ledger.summary()["requests_used"] == 1
    client.close()
