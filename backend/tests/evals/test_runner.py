import copy
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from evals.aggregate import runner
from evals.aggregate.cli import main
from evals.aggregate.execution import execute, offline_guards
from evals.aggregate.results import metrics, normalize, render
from evals.aggregate.schema import Config, digest, load_inputs, verify_freeze, write_json


def test_isolated_orders_funding_and_correction_history(inputs, evidence, tmp_path):
    ids, payment_ids = set(), set()
    normalized = []
    for case, expected in zip(*inputs, strict=True):
        public = tmp_path / case.id
        public.mkdir()
        result = normalize(case, expected, evidence / case.id, public, {"status": "completed"})
        normalized.append(result)
        accepted = json.loads((evidence / case.id / "accepted.json").read_bytes())
        assert not accepted["deliveries"] and not accepted["authorization"]["receipt"]
        assert accepted["snapshot"]["quote"]["policy"]["version"] == "aggregate-brokerage-v1"
        ids.add(accepted["snapshot"]["order_id"])
        payment_ids.add(accepted["payment_id"])
    assert len(ids) == len(payment_ids) == 6
    # The whole-claim offline guard no longer dismisses this phrasing by keyword.
    # Keep the frozen FAIL label: the evaluator must expose UNKNOWN as a mismatch,
    # not relabel it as a successful evaluation or teach runtime the expected answer.
    assert [r["outcome"] for r in normalized] == [
        "match",
        "match",
        "mismatch",
        "match",
        "mismatch",
        "mismatch",
    ]
    initial, corrected = normalized[1]["checkpoints"]
    assert initial["finding_scope"] == "historical_attempt_before_invalidation"
    assert initial["artifact_audit"]["status"] == "invalid"
    assert initial["action"] == "correct" and corrected["action"] == "publish"
    assert all(r["raw_model"] is None for r in initial["requirements"])
    assert any(r["effective"] == "FAIL" for r in initial["requirements"])
    assert all(r["effective"] == "PASS" for r in corrected["requirements"])
    money = normalized[0]["checkpoints"][-1]["financial"]
    assert money["state"] == "captured" and money["simulated"]
    assert len(money["bookings"]) == 1
    assert money["bookings"][0]["receipt"]["transaction_id"] is None
    claim = normalized[2]["checkpoints"][-1]["complaint"]
    assert claim["effective"] == "UNKNOWN" and claim["expected"] == "FAIL"
    assert "complaint:complaint_result" in normalized[2]["mismatches"]
    assert any(m.startswith("complaint:action:") for m in normalized[2]["mismatches"])
    saved = json.loads((evidence / "D03/checkpoint-complaint.json").read_bytes())
    case = saved["order"]["cases"][-1]
    assert case["status"] == "open" and case["questions_asked"] == 1 and case["question"]
    assert normalized[2]["checkpoints"][-1]["financial"]["bookings"] == []
    child = json.loads((evidence / "D04/accepted-child.json").read_bytes())
    assert child["snapshot"]["quote"]["amount"]["amount_minor"] == 50
    assert child["authorization"]["receipt"] is None
    m = metrics(normalized)
    assert m["development/engineering"]["agreement"] == {
        "numerator": 78,
        "denominator": 80,
        "value": 0.975,
    }
    assert m["held_out/rehan_reviewed"]["agreement"]["value"] is None


def test_false_pass_missing_contradiction_abstention_and_raw_absence():
    rows = [
        {"effective": actual, "expected": expected, "comparison": comparison}
        for actual, expected, comparison in [
            ("PASS", "FAIL", "mismatch"),
            ("PASS", "CONFLICT", "mismatch"),
            ("UNKNOWN", "PASS", "mismatch"),
            ("UNKNOWN", "UNKNOWN", "match"),
            (None, "PASS", "unscored"),
        ]
    ]
    result = metrics(
        [
            {
                "classification": "held_out",
                "review_status": "rehan_reviewed",
                "checkpoints": [{"requirements": rows}],
            }
        ]
    )["held_out/rehan_reviewed"]
    assert result["scheduled_requirement_observations"] == 5
    assert result["false_pass"]["numerator"] == 2
    assert result["missed_contradiction"]["value"] == 1
    assert result["excessive_abstention"]["denominator"] == 3
    assert result["agreement"]["denominator"] == 5 and result["agreement"]["numerator"] == 1
    assert result["raw_model_errors"]["value"] is None


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "wrong_requirement", "wrong_case", "split", "extra"]
)
def test_strict_labels(inputs, tmp_path, mutation):
    cases, expected = inputs
    data = {
        "schema_version": "aggregate-expectations-v1",
        "expectations": [e.model_dump() for e in expected],
    }
    item = data["expectations"][0]
    labels = item["checkpoints"][0]["requirements"]
    if mutation == "missing":
        labels.pop()
    elif mutation == "duplicate":
        labels.append(labels[0])
    elif mutation == "wrong_requirement":
        labels[0]["requirement_id"] = "R-OTHER"
    elif mutation == "wrong_case":
        item["case_id"] = "OTHER"
    elif mutation == "split":
        item["classification"] = "held_out"
    else:
        item["gold_in_runtime"] = "forbidden"
    write_json(
        tmp_path / "cases.json",
        {"schema_version": "aggregate-cases-v1", "cases": [c.model_dump() for c in cases]},
    )
    write_json(tmp_path / "expectations.json", data)
    with pytest.raises(ValueError):
        load_inputs(tmp_path / "cases.json", tmp_path / "expectations.json")


def test_validation_listing_and_help_create_no_runtime(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runner, "run", lambda *a: pytest.fail("validation created runtime work"))
    assert main(["list", "--case", "D01"]) == 0
    assert main(["validate"]) == 0
    assert main(["validate", "--case", "bad"]) == 2
    for command in [[], ["run"]]:
        with pytest.raises(SystemExit) as exit:
            main([*command, "--help"])
        assert exit.value.code == 0
        assert "Example" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_invalid_output_path_creates_no_runtime(tmp_path, monkeypatch):
    output = tmp_path / "existing-file"
    output.write_text("preserve")
    monkeypatch.setattr(runner, "run", lambda *args: pytest.fail("invalid input created runtime"))
    assert main(["run", "--output", str(output)]) == 2
    assert output.read_text() == "preserve"


def test_report_storage_error_is_operational_not_quality_failure(tmp_path, monkeypatch, capsys):
    def fail(*args):
        raise PermissionError("token=SECRET_URL_CANARY")

    monkeypatch.setattr(runner, "run", fail)
    assert main(["run", "--output", str(tmp_path)]) == 3
    assert "SECRET_URL_CANARY" not in capsys.readouterr().err


def test_network_provider_guards_ignore_ambient_opt_in(monkeypatch):
    from anthropic import Anthropic

    from app.agents.gateway import ClaudeGateway
    from app.payments.base import BasePaymentTransport

    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    monkeypatch.setenv("PAYMENT_ADAPTER", "base_sepolia")
    with offline_guards():
        for call in [
            lambda: ClaudeGateway(enabled=True, client=object()),
            Anthropic,
            BasePaymentTransport,
            lambda: socket.getaddrinfo("example.com", 443),
        ]:
            with pytest.raises(RuntimeError, match="offline_evaluation"):
                call()
        with socket.socket() as client, pytest.raises(RuntimeError, match="offline_evaluation"):
            client.connect(("127.0.0.1", 1234))


def test_freeze_tamper_is_detected(tmp_path):
    path = tmp_path / "plan.json"
    plan = {"expectation": "FAIL", "seed": 0}
    write_json(path, {"plan": plan, "sha256": digest(plan)})
    assert verify_freeze(path)["plan"] == plan
    data = json.loads(path.read_bytes())
    data["plan"]["expectation"] = "PASS"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_freeze(path)


def inline_case(case, directory, config):
    directory.mkdir()
    details = execute(case.recipe, directory, config.max_steps)
    return {"status": "completed", **details}


def test_leakage_stable_report_additive_runs_and_no_gold_claim(inputs, tmp_path, monkeypatch):
    cases, expected = inputs
    canary = "EXPECTATION_CANARY_NEVER_SEND_TO_RUNTIME_93A7"
    label = expected[0].model_copy(update={"review_rationale": canary})
    monkeypatch.setattr(runner, "run_case", inline_case)
    directory, result = runner.run(cases[:1], [label], Config(), tmp_path)
    assert result["exit_code"] == 0 and result["qualification"] == "not_claimed"
    assert canary in (directory / "private/frozen-plan.json").read_text()
    for path in (directory / "private/D01").rglob("*.json"):
        assert canary not in path.read_text()
    assert (directory / "report.md").read_text() == render(result) == render(copy.deepcopy(result))
    old = (directory / "results.json").read_bytes()
    second, _ = runner.run(cases[:1], [label], Config(), tmp_path)
    assert second != directory and (directory / "results.json").read_bytes() == old
    assert result["usage"] is None and result["cost"] is None


def test_real_child_timeout_then_unrelated_case_continues(inputs, tmp_path, monkeypatch):
    cases, expected = inputs
    original = runner.run_case

    def dispatch(case, directory, config):
        return original(case, directory, Config(case_seconds=0.001) if case.id == "D01" else config)

    monkeypatch.setattr(runner, "run_case", dispatch)
    directory, result = runner.run(cases[:2], expected[:2], Config(), tmp_path)
    assert result["exit_code"] == 3
    assert result["cases"][0]["operation"]["status"] == "timeout"
    assert result["cases"][1]["outcome"] == "match"
    assert result["metrics"]["development/engineering"]["agreement"]["denominator"] == 32
    assert (directory / "report.md").exists()


def test_step_limit_preserves_partial_state_and_reports(inputs, tmp_path):
    directory, result = runner.run(inputs[0][:1], inputs[1][:1], Config(max_steps=1), tmp_path)
    assert result["exit_code"] == 3
    assert result["cases"][0]["operation"]["error"] == "StepLimit"
    assert (directory / "private/D01/orders.sqlite3").exists()
    assert result["metrics"]["development/engineering"]["agreement"]["numerator"] == 0


def test_missing_expectations_and_tampered_run_remain_incomplete(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run_case", inline_case)
    _, result = runner.run(inputs[0][:1], [], Config(), tmp_path)
    assert result["exit_code"] == 3 and result["incomplete"] == 1
    assert result["metrics"]["development/missing"]["unscored"] == 16

    def tamper(case, directory, config):
        outcome = inline_case(case, directory, config)
        freeze = directory.parent / "frozen-plan.json"
        envelope = json.loads(freeze.read_bytes())
        envelope["plan"]["config"]["seed"] = 2
        freeze.write_text(json.dumps(envelope))
        return outcome

    monkeypatch.setattr(runner, "run_case", tamper)
    directory, result = runner.run(inputs[0][:1], inputs[1][:1], Config(), tmp_path)
    assert result["exit_code"] == 3 and result["errors"]
    assert "tampering" in (directory / "report.md").read_text()


def test_no_production_evaluator_imports():
    root = Path(__file__).resolve().parents[2] / "app"
    assert not any("evals.aggregate" in p.read_text() for p in root.rglob("*.py"))


def test_child_environment_and_error_output_are_private(inputs, tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        assert "API_KEY" not in kwargs["env"]
        assert kwargs["env"]["PAYMENT_ADAPTER"] == "mock"
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setenv("API_KEY", "secret-canary")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_case(inputs[0][0], tmp_path / "case", Config())
    assert result["status"] == "error" and result["exit_code"] == 7


def test_false_passing_observation_is_not_repaired_by_evaluator(inputs, evidence, tmp_path):
    directory = tmp_path / "case"
    shutil.copytree(evidence / "D02", directory)
    path = directory / "checkpoint-initial.json"
    saved = json.loads(path.read_bytes())
    for finding in saved["attempt"]["verification"]["assessments"]:
        if finding["obligation_id"] == "dataset:coverage":
            finding["result"] = "PASS"
    path.write_text(json.dumps(saved))
    public = tmp_path / "public"
    public.mkdir()
    result = normalize(inputs[0][1], inputs[1][1], directory, public, {"status": "completed"})
    row = next(
        r for r in result["checkpoints"][0]["requirements"] if r["requirement_id"] == "R-COVERAGE"
    )
    assert row["effective"] == "PASS" and row["expected"] == "FAIL"
    assert row["comparison"] == "mismatch" and result["outcome"] == "mismatch"


def test_tampered_preview_invalidates_case_and_unsupported_refs_are_unscored(
    inputs, evidence, tmp_path
):
    directory = tmp_path / "case"
    shutil.copytree(evidence / "D01", directory)
    path = directory / "checkpoint-delivery.json"
    saved = json.loads(path.read_bytes())
    preview = saved["attempt"]["output"]["preview"]
    (directory / "artifacts" / preview["storage_key"]).write_text("{}")
    finding = saved["order"]["verification"]["assessments"][0]
    finding["citations"] = [finding["citations"][0] | {"kind": "pdf"}]
    path.write_text(json.dumps(saved))
    public = tmp_path / "public"
    public.mkdir()
    result = normalize(inputs[0][0], inputs[1][0], directory, public, {"status": "completed"})
    assert result["outcome"] == "incomplete"
    assert result["mismatches"]
    assert result["checkpoints"][0]["requirements"][0]["comparison"] == "unscored"
    assert not result["checkpoints"][0]["artifact_audit"]["files"]


def test_unsafe_original_count_and_credentials_never_reach_readable_report(
    inputs, evidence, tmp_path, monkeypatch
):
    from tests.evals.test_audit import artifact

    def unsafe(case, directory, config):
        shutil.copytree(evidence / "D01", directory)
        for name in ("delivery", "settled"):
            path = directory / f"checkpoint-{name}.json"
            saved = json.loads(path.read_bytes())
            csv = saved["attempt"]["output"]["csv"]
            raw = (directory / "artifacts" / csv["storage_key"]).read_bytes()
            # This intentionally unsafe engineering value must stay private.
            replacement = artifact(
                directory / "artifacts", raw.replace(b",,suppressed", b",37,suppressed"), "text/csv"
            )
            saved["attempt"]["output"]["csv"] = replacement
            path.write_text(json.dumps(saved))
        return {"status": "completed"}

    monkeypatch.setattr(runner, "run_case", unsafe)
    label = inputs[1][0].model_copy(
        update={"review_rationale": "token=SECRET_CANARY https://user:password@host/key"}
    )
    directory, result = runner.run(inputs[0][:1], [label], Config(), tmp_path)
    text = (directory / "report.md").read_text()
    assert "unsafe_nonreleased_count" in text
    assert ",37,suppressed" not in text and "count': 37" not in text
    assert "SECRET_CANARY" not in text and "user:password" not in text
    assert list((directory / "artifacts").iterdir()) == []
    assert result["exit_code"] == 1


@pytest.mark.parametrize("damaged", ["delivery", "settled"])
@pytest.mark.parametrize("payload,error", [('{"order":', "JSONDecodeError"), ("{}", "KeyError")])
def test_checkpoint_errors_preserve_other_results_and_timeout(
    inputs, evidence, tmp_path, monkeypatch, damaged, payload, error
):
    case, expected = inputs[0][0], inputs[1][0]
    public = tmp_path / "baseline"
    public.mkdir()
    operation = {"status": "timeout", "error": "case_wall_clock_limit"}
    baseline = normalize(case, expected, evidence / case.id, public, operation)

    def interrupted(case, directory, config):
        shutil.copytree(evidence / case.id, directory)
        (directory / f"checkpoint-{damaged}.json").write_text(payload)
        return operation.copy()

    monkeypatch.setattr(runner, "run_case", interrupted)
    directory, report = runner.run([case], [expected], Config(), tmp_path)
    assert json.loads((directory / "results.json").read_bytes()) == report
    result = report["cases"][0]
    assert result["operation"] == operation
    assert result["outcome"] == "incomplete" and report["exit_code"] == 3
    assert f"{damaged}:audit_{error}" in result["unavailable"]
    assert (directory / f"private/{case.id}/checkpoint-{damaged}.json").read_text() == payload
    text = (directory / "report.md").read_text()
    assert "case_wall_clock_limit" in text and f"{damaged}:audit_{error}" in text
    for checkpoint, original in zip(result["checkpoints"], baseline["checkpoints"], strict=True):
        if checkpoint["id"] == damaged:
            assert checkpoint["financial"] is None
            assert all(row["comparison"] == "unscored" for row in checkpoint["requirements"])
        else:
            assert checkpoint == original
            assert all(row["effective"] == "PASS" for row in checkpoint["requirements"])
            money = checkpoint["financial"]
            assert f"Mock payment: {money['state']}" in text
            assert f"observed bookings {len(money['bookings'])}" in text
            for artifact in checkpoint["artifact_audit"]["files"]:
                assert (directory / artifact["path"]).is_file()
    group = report["metrics"]["development/engineering"]
    assert group["scheduled_requirement_observations"] == 16
    assert group["unscored"] == 8
    assert group["agreement"]["numerator"] == 8
