"""No-network wiring checks for the separate, explicitly authorized qualification."""

import json
from types import SimpleNamespace

import aggregate_qualification as harness
from app.agents.gateway import ClaudeGateway
from tests.dataset.test_intake_conversation import ModelIntent


def test_http_qualification_records_actual_questions_without_labels_in_runtime(tmp_path):
    class Conversation(ModelIntent):
        def parse(self, **kwargs):
            payload = json.loads(kwargs["messages"][0]["content"])
            answers = payload["draft"]["answers"]
            self.scope = (
                "ambiguous"
                if not answers
                else "gym_only"
                if answers[-1]["text"] == "gym membership"
                else "gym_or_fitness_app"
            )
            assert "basis" not in payload and "expected" not in payload
            return super().parse(**kwargs)

    fake = Conversation()
    gateway = ClaudeGateway(
        enabled=True, model="claude-opus-5-5", client=SimpleNamespace(messages=fake)
    )
    result = harness.evaluate_intake(harness.INTAKE[0], tmp_path, compiler=gateway)
    assert result["acceptance_pass"] and result["calls"] == 3
    assert result["model_authored_questions"] == 1
    assert len(list((tmp_path / "I1").glob("call-*.json"))) == 3
    transcript = json.loads((tmp_path / "I1/transcript.json").read_text())
    assert transcript[1]["question_origin"] == "rules"
    assert transcript[1]["draft"]["specification"] is None
    assert transcript[2]["draft"]["specification"]["terms"]["category"] == "gym_or_fitness_app"
