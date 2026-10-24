"""Secret-safe organization model check and one budgeted structured-output request.

Load the user-designated private file with uv --env-file. This script never opens,
copies, logs or returns credentials and never trusts a custom provider endpoint.
"""

import json
import os
import time
from pathlib import Path

import anthropic
from pydantic import BaseModel, ConfigDict

from app.agents.budget import ModelBudget


class Smoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


def main():
    model = os.environ["CLAUDE_MODEL"]
    budget = ModelBudget.configured()
    report = {"requested_model": model, "key_present": bool(os.getenv("ANTHROPIC_API_KEY")),
              "paid_calls_enabled": os.getenv("ENABLE_PAID_MODELS") == "true"}
    client = anthropic.Anthropic(base_url="https://api.anthropic.com", timeout=25, max_retries=0)
    identifier = None
    started = time.monotonic()
    try:
        metadata = client.models.retrieve(model)
        report["organization_model_available"] = True
        report["resolved_model"] = metadata.id
        payload = {"messages": [{"role": "user", "content": 'Return {"ok": true} as a configuration smoke test.'}],
                   "schema": Smoke.model_json_schema()}
        identifier = budget.reserve("authenticated-schema-smoke", model, payload, 512)
        started = time.monotonic()
        response = client.messages.parse(model=model, max_tokens=512, messages=payload["messages"], output_format=Smoke)
        budget.finish(identifier, response.usage)
        report.update({"actual_model": response.model, "latency_seconds": round(time.monotonic()-started, 3),
                       "usage": response.usage.model_dump(mode="json"), "stop_reason": response.stop_reason,
                       "success": response.parsed_output is not None and response.parsed_output.ok,
                       "response": response.parsed_output.model_dump() if response.parsed_output else None})
    except Exception as error:
        if identifier:
            budget.finish(identifier, failed=True)
        report.update({"success": False, "error_type": type(error).__name__,
                       "http_status": getattr(error, "status_code", None),
                       "latency_seconds": round(time.monotonic()-started,3)})
        if isinstance(error, anthropic.APIStatusError):
            body = error.body if isinstance(error.body, dict) else {}
            detail = body.get("error", {})
            report["provider_error_type"] = detail.get("type") if isinstance(detail, dict) else None
    finally:
        client.close()
    report["budget"] = budget.summary()
    output = Path(__file__).resolve().parents[1] / "backend/artifacts/v6-model-smoke.json"
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
