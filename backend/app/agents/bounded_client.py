"""Budget every real SDK request, including failed/uncertain attempts; no SDK retries."""

import os
from datetime import UTC, datetime
from types import SimpleNamespace

import anthropic

from app.agents.budget import ModelBudget


def selected_model():
    # Legacy name is decoding compatibility for old injected tests/configuration;
    # all new live configuration uses CLAUDE_MODEL and the budget enforces its ID.
    return os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL")


def envelope(kwargs):
    return {
        key: value.model_json_schema() if hasattr(value, "model_json_schema") else value
        for key, value in kwargs.items()
    }


def failure_metadata(error):
    cooldown = 0
    if isinstance(error, anthropic.RateLimitError):
        try:
            cooldown = max(1, float(error.response.headers.get("retry-after", "60")))
        except (ValueError, AttributeError):
            cooldown = 60
    return {"failed": True, "failure_signature": type(error).__name__, "cooldown_seconds": cooldown}


def remaining_timeout(budget):
    return max(0.001, min(60.0, (budget.cutoff - datetime.now(UTC)).total_seconds()))


class BoundedClient:
    def __init__(self, *, purpose="catalog", client=None, budget=None, final_evaluation=False):
        self.budget = budget or ModelBudget.configured()
        self.client = client or anthropic.Anthropic(
            base_url="https://api.anthropic.com", timeout=60.0, max_retries=0
        )
        self.purpose = purpose
        self.messages = self
        self.last_response = None
        self.response_sink = None
        self.final_evaluation = final_evaluation
        self.last_call_id = None

    def parse(self, **kwargs):
        self.last_response = None
        call = self.budget.reserve(
            self.purpose,
            kwargs["model"],
            envelope(kwargs),
            kwargs["max_tokens"],
            final_evaluation=self.final_evaluation,
        )
        self.last_call_id = call
        try:
            if hasattr(self.client.messages, "with_raw_response"):
                from anthropic.lib._parse._transform import transform_schema

                schema = kwargs["output_format"]
                wire = {key: value for key, value in kwargs.items() if key != "output_format"}
                wire["output_config"] = {
                    "format": {
                        "type": "json_schema",
                        "schema": transform_schema(schema.model_json_schema()),
                    }
                }
                raw = self.client.messages.with_raw_response.create(
                    **wire, timeout=remaining_timeout(self.budget)
                )
                self.last_response = raw.http_response.json()
                self.budget.finish(call, self.last_response.get("usage"))
                if self.response_sink:
                    self.response_sink(self.last_response)
                # The original response is saved before schema parsing, including
                # malformed/refused output. No semantic repair is performed here.
                response = raw.parse()
                parsed = None
                if response.stop_reason == "end_turn":
                    text = "".join(block.text for block in response.content if block.type == "text")
                    parsed = schema.model_validate_json(text)
                return SimpleNamespace(
                    stop_reason=response.stop_reason,
                    parsed_output=parsed,
                    model_dump=response.model_dump,
                )
            result = self.client.messages.parse(**kwargs)
        except BaseException as error:
            self.budget.finish(call, **failure_metadata(error))
            raise
        self.budget.finish(call, result.usage)
        return result

    def close(self):
        self.client.close()


class BoundedAsyncClient:
    def __init__(self, *, purpose="improvement", client=None, budget=None):
        self.budget = budget or ModelBudget.configured()
        self.client = client or anthropic.AsyncAnthropic(
            base_url="https://api.anthropic.com", timeout=60.0, max_retries=0
        )
        self.purpose = purpose
        self.messages = self
        self.last_call_id = None

    async def create(self, **kwargs):
        # Opus 5.5 has always-on adaptive thinking and rejects forced tool use.
        # A real call may choose the schema tool; the domain rejects missing output.
        if kwargs.get("tool_choice", {}).get("type") == "tool":
            kwargs = {**kwargs, "tool_choice": {"type": "auto"}}
        call = self.budget.reserve(
            self.purpose, kwargs["model"], envelope(kwargs), kwargs["max_tokens"]
        )
        self.last_call_id = call
        try:
            result = await self.client.messages.create(
                **kwargs, timeout=remaining_timeout(self.budget)
            )
        except BaseException as error:
            self.budget.finish(call, **failure_metadata(error))
            raise
        self.budget.finish(call, result.usage)
        return result

    async def close(self):
        await self.client.close()
