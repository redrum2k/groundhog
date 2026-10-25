import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.audit_model_journey import match_response


def response():
    return {
        "model": "test-model",
        "stop_reason": "end_turn",
        "id": "msg_test",
        "usage": {"input_tokens": 7},
    }


def call(identifier, digest, *, purpose="primary-dataset-dispute", usage=7):
    return {
        "id": identifier,
        "request_sha256": digest,
        "model": "test-model",
        "purpose": purpose,
        "usage_json": json.dumps({"input_tokens": usage}),
    }


def test_identical_usage_does_not_match_an_unrelated_request():
    unrelated, expected = call("other", "other-hash"), call("actual", "expected-hash")
    calls = [unrelated, expected]
    matched = match_response(
        response(),
        calls,
        request_hash="expected-hash",
        model="test-model",
        purpose="primary-dataset-dispute",
    )
    assert matched["call_id"] == "actual"
    assert calls == [unrelated]


@pytest.mark.parametrize(
    "calls",
    [
        [call("unrelated", "wrong")],
        [call("a", "expected"), call("b", "expected")],
        [call("wrong-purpose", "expected", purpose="intake")],
        [call("wrong-usage", "expected", usage=8)],
    ],
)
def test_missing_ambiguous_or_inconsistent_dispatch_fails_closed(calls):
    before = list(calls)
    with pytest.raises(AssertionError):
        match_response(
            response(),
            calls,
            request_hash="expected",
            model="test-model",
            purpose="primary-dataset-dispute",
        )
    assert calls == before
