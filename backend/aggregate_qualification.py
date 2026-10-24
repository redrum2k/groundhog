"""One-off real HTTP/Claude qualification, not the general aggregate evaluation runner.

Reuse the completed primary dispute harness. Freeze this new cohort before calls;
do not rerun/regrade its cases after inspecting results. Expected answers stay here,
outside the runtime request packets. The parent independently bounds its child.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import primary_followup_eval as primary
from aggregate_qualification_access import CUTOFF, OUTPUT, WINDOW, configured_window
from app.agents.bounded_client import BoundedClient, envelope
from app.contracts.catalog import ClarifyCommand, RevisionCommand
from app.main import create_app

INTAKE = (
    dict(
        id="I1",
        prompt="SF adults 25–34 interested in fitness, counts by ZIP.",
        answers=["gym membership", "yes"],
        status="ready",
        category="gym_or_fitness_app",
        basis="Exact reported conversation; broader-product consent is a separate answer.",
    ),
    dict(
        id="I2",
        prompt="SF adults 25-34, gym membership only, no fitness apps, counts by ZIP.",
        answers=["no"],
        status="human_review",
        category=None,
        basis="Narrow product unavailable; refusal is not acceptance.",
    ),
    dict(
        id="I3",
        prompt="SF adults 18-24, gym membership or fitness-app use, counts by ZIP.",
        answers=["Correct that to San Francisco adults 25-34, grouped by ZIP."],
        status="ready",
        category="gym_or_fitness_app",
        basis="Question-bound cohort correction replaces that field without altering history.",
    ),
    dict(
        id="I4",
        prompt="SF adults 25-34, gym membership or fitness-app use. Don't include yoga.",
        answers=[],
        status="ready",
        category="gym_or_fitness_app",
        basis="Explicit yoga exclusion must not become yoga-inclusive terms.",
    ),
    dict(
        id="I5",
        prompt="SF adults 25-34: people paying for the weight room, not workout software.",
        answers=["Yes, the combined product is fine."],
        status="ready",
        category="gym_or_fitness_app",
        basis="Semantic paraphrase, then explicit broader consent.",
    ),
    dict(
        id="I6",
        prompt="SF adults 25-34, gym membership or fitness app use. Include yoga but exclude yoga.",
        answers=["Exclude yoga."],
        status="ready",
        category="gym_or_fitness_app",
        basis="Conflicting category instructions require a material, bound correction.",
    ),
)

DISPUTES = (
    dict(
        id="D1",
        expanded=True,
        text="Standalone yoga memberships are covered by our accepted scope.",
        expected="PASS",
        basis="Accepted expansion plus frozen category evidence; not provider-output fault.",
    ),
    dict(
        id="D2",
        expanded=False,
        field="coverage",
        product="94110",
        text="ZIP 94110 is missing from the delivered CSV.",
        expected="FAIL",
        basis="Independently inspect actual CSV and frozen coverage for 94110.",
    ),
    dict(
        id="D3",
        expanded=False,
        text="The agreed fitness audience was supposed to be investor-ready.",
        expected="UNKNOWN",
        basis="No accepted definition or authority establishes investor-ready.",
    ),
    dict(
        id="D4",
        expanded=False,
        taxonomy=None,
        text="Under the agreed definition, yoga counts as gym membership.",
        expected="UNKNOWN",
        basis="Null taxonomy does not establish equivalence; missing authority stays unknown.",
    ),
    dict(
        id="D5",
        expanded=False,
        text=(
            "The agreed population does not count a person whose only activity is standalone yoga."
        ),
        expected="PASS",
        basis="New negative-scope paraphrase; explicit exclusion is accepted.",
    ),
)
FOLLOWUP = (
    dict(
        id="F1",
        expanded=False,
        taxonomy=None,
        text="Under our agreed terms, standalone yoga qualifies as gym membership.",
        expected="UNKNOWN",
        basis="Fresh taxonomy paraphrase; null is missing authority, not false.",
    ),
    dict(
        id="F2",
        expanded=False,
        text="Our accepted cohort doesn't include people whose only membership is standalone yoga.",
        expected="PASS",
        basis="Fresh scope-first negative form under accepted exclusion.",
    ),
    dict(
        id="F3",
        expanded=True,
        text="The agreed population includes adults whose only activity is standalone yoga.",
        expected="PASS",
        basis="Positive scope-first counterpart under an explicitly expanded contract.",
    ),
    dict(
        id="F4",
        expanded=False,
        text="Standalone yoga satisfies the agreed gym membership category.",
        expected="FAIL",
        basis="A false taxonomy cell contradicts equivalence; not automatic UNKNOWN.",
    ),
    dict(
        id="F5",
        expanded=False,
        text="Our accepted definition guarantees wellness-ready prospects.",
        expected="UNKNOWN",
        basis="Undefined quality language still lacks an accepted metric.",
    ),
)
CONFIRMATION = (
    dict(
        id="C1",
        prompt="SF adults 18-24, gym membership or fitness-app use; counts by ZIP.",
        answers=["yes"],
        status="ready",
        category="gym_or_fitness_app",
        basis="A bare yes accepts only the displayed, explicitly bound supported-cohort offer.",
    ),
    dict(
        id="C2",
        prompt="Oakland adults 25-34, gym membership or fitness-app use, by ZIP.",
        answers=["no"],
        status="human_review",
        category=None,
        basis="Declining the selected SF corpus offer does not silently change geography.",
    ),
    dict(
        id="C3",
        prompt="San Francisco adults aged 25-34 interested in fitness, ZIP counts.",
        answers=["gym membership", "yes"],
        status="ready",
        category="gym_or_fitness_app",
        require_broader_consent=True,
        basis="Fresh revalidation of narrow answer plus separate union-product consent.",
    ),
    dict(
        id="C4",
        prompt=(
            "San Francisco adults 25-34, gym membership or fitness-app use. Do not include yoga."
        ),
        answers=[],
        status="ready",
        category="gym_or_fitness_app",
        basis="Explicit exclusion retained after cohort-confirmation fix.",
    ),
)
COHORTS = {
    "pilot": (INTAKE, DISPUTES),
    "followup": ((), FOLLOWUP),
    "confirmation": (CONFIRMATION, ()),
}


def observe(gateway, target):
    """Record the actual guarded transport; do not replace its SDK or budget logic."""
    client = gateway.client
    original = client.messages.parse
    calls = []

    def traced(**kwargs):
        started = time.monotonic()
        record = dict(request=envelope(kwargs), started_at=datetime.now(UTC).isoformat())
        if hasattr(client, "last_call_id"):
            client.last_call_id = None
        try:
            response = original(**kwargs)
            record["parsed"] = (
                response.parsed_output.model_dump(mode="json") if response.parsed_output else None
            )
            return response
        except Exception as error:
            record.update(
                error_type=type(error).__name__, status_code=getattr(error, "status_code", None)
            )
            raise
        finally:
            record.update(
                latency_seconds=time.monotonic() - started,
                call_id=getattr(client, "last_call_id", None),
                raw_response=getattr(client, "last_response", None),
            )
            calls.append(record)
            primary.save(target / f"call-{len(calls)}.json", record)

    client.messages.parse = traced
    return calls


def evaluate_intake(recipe, root, *, compiler=None):
    target = root / recipe["id"]
    target.mkdir(exist_ok=False)
    app = create_app(
        target / "orders.sqlite3",
        artifact_root=target / "artifacts",
        run_worker=False,
        compiler=compiler,
        payment_mode="mock",
        internal_token="qualification-worker",
        reviewer_token="qualification-reviewer",
    )
    transcript, invariants = [], []
    with TestClient(app) as client:
        service = app.state.orders
        gateway = service.dataset_compiler
        if not hasattr(gateway, "interpret_dataset"):
            raise RuntimeError("Expected genuine dataset-specific Claude intake wiring")
        calls = observe(gateway, target)
        run = primary.post(client, "/runs", {"prompt": recipe["prompt"]}, "create")["id"]
        initial = service.get_request(run)
        try:
            for turn in range(len(recipe["answers"]) + 1):
                draft = service.get_request(run)
                if turn:
                    if draft.status != "clarification":
                        break
                    payload = ClarifyCommand(
                        expected_revision=draft.revision,
                        idempotency_key=f"answer:{turn}",
                        question_id=draft.question.question_id,
                        text=recipe["answers"][turn - 1],
                    ).model_dump(mode="json")
                    primary.post(client, f"/requests/{run}/answers", payload)
                    draft = service.get_request(run)
                command = RevisionCommand(
                    expected_revision=draft.revision,
                    idempotency_key=f"compile:{turn}",
                ).model_dump(mode="json")
                response = client.post(
                    f"/internal/requests/{run}/compile",
                    json=command,
                    headers={"X-Internal-Token": "qualification-worker"},
                )
                if response.status_code != 200:
                    raise RuntimeError(f"Intake compile HTTP {response.status_code}")
                current = service.get_request(run)
                count = len(calls)
                replay = client.post(
                    f"/internal/requests/{run}/compile",
                    json=command,
                    headers={"X-Internal-Token": "qualification-worker"},
                )
                assert replay.json() == response.json() and len(calls) == count
                assert current.prompt == initial.prompt and current.deadline == initial.deadline
                assert current.questions_asked <= 2 and current.compiler_calls <= 4
                page = client.get(f"/runs/{run}/events").json()
                assert page["payment"] is None and page["quote"] is None
                assert not {"contract_approved", "payment_captured"} & {
                    e["type"] for e in page["events"]
                }
                proposal = calls[-1].get("parsed") if calls else None
                transcript.append(
                    dict(
                        turn=turn,
                        buyer=recipe["prompt"] if turn == 0 else recipe["answers"][turn - 1],
                        draft=current.model_dump(mode="json"),
                        proposal=proposal,
                        question_origin=(
                            "model"
                            if proposal
                            and current.question
                            and current.question.prompt == proposal.get("clarification")
                            else "rules"
                            if current.question
                            else None
                        ),
                    )
                )
                if current.status != "clarification":
                    break
            final = service.get_request(run)
            questions = [q.prompt for q in final.question_history]
            assert len(questions) == len(set(" ".join(q.lower().split()) for q in questions))
            category = final.specification.terms.category if final.specification else None
            correct = final.status == recipe["status"] and category == recipe["category"]
            if recipe["id"] == "I1" or recipe.get("require_broader_consent"):
                correct &= len(final.answers) == 2 and any(
                    q.field == "category_offer_base" for q in final.question_history
                )
            invariants = [
                "unchanged_history_deadline",
                "no_financial_effects",
                "bounded_questions",
                "no_identical_question",
                "compile_replay_no_call",
            ]
            result = dict(
                case=recipe["id"],
                lane="intake",
                status=final.status,
                category=category,
                expected_status=recipe["status"],
                expected_category=recipe["category"],
                acceptance_pass=bool(correct),
                questions=questions,
                model_authored_questions=sum(
                    row["question_origin"] == "model" for row in transcript
                ),
                calls=len(calls),
                invariant_checks=invariants,
            )
            primary.save(target / "transcript.json", transcript)
            primary.save(target / "events.json", client.get(f"/runs/{run}/events").json())
            primary.save(target / "request.json", final.model_dump(mode="json"))
            primary.save(target / "result.json", result)
            print(json.dumps(result), flush=True)
            return result
        finally:
            if hasattr(gateway.client, "close"):
                gateway.client.close()


def child(cohort):
    budget = configured_window()
    root = OUTPUT / cohort
    intake, disputes = COHORTS[cohort]
    plan = dict(
        cohort=cohort,
        window=WINDOW,
        cutoff=CUTOFF,
        intake=intake,
        disputes=disputes,
        source_sha256=primary.source_hash(),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        model=os.environ["CLAUDE_MODEL"],
        output_tokens=4096,
        timeout_seconds=20,
        retries=0,
        concurrency=1,
        final_reserve="Existing $10 unchanged",
        qualification="Scenario acceptance, not independently reviewed held-out accuracy",
        recovery="Preserve failures; fixes require a separately named fresh-order cohort",
    )
    primary.save(root / "frozen-plan.json", plan)
    before = budget.summary()
    metadata_client = BoundedClient(purpose="qualification-metadata", budget=budget)
    try:
        available = metadata_client.client.models.retrieve(os.environ["CLAUDE_MODEL"])
        primary.save(
            root / "model-availability.json",
            dict(id=available.id, checked_at=datetime.now(UTC).isoformat()),
        )
    finally:
        metadata_client.close()
    os.environ["ENABLE_DATASET_MODEL_ASSESSMENT"] = "true"
    os.environ["ENABLE_BROKER_DISPUTE_ASSESSMENT"] = "false"
    primary.OUTPUT = root  # Only this process; original frozen evidence is never touched.
    results = []
    for lane, recipes in (("intake", intake), ("dispute", disputes)):
        for recipe in recipes:
            if datetime.now(UTC) >= datetime.fromisoformat(CUTOFF):
                break
            try:
                result = (
                    evaluate_intake(recipe, root) if lane == "intake" else primary.evaluate(recipe)
                )
                results.append(result)
            except Exception as error:
                result = dict(
                    case=recipe["id"],
                    lane=lane,
                    status="HARNESS_OR_RUNTIME_FAILURE",
                    error_type=type(error).__name__,
                )
                primary.save(root / (recipe["id"] + "-failure.json"), result)
                results.append(result)
                print(json.dumps(result), flush=True)
    primary.save(
        root / "results.json",
        dict(
            before=before,
            after=budget.summary(),
            source_sha256=primary.source_hash(),
            cases=results,
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=COHORTS, default="pilot")
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    if args.child:
        child(args.cohort)
        return
    remaining = (datetime.fromisoformat(CUTOFF) - datetime.now(UTC)).total_seconds()
    if remaining < 300:
        raise RuntimeError("Insufficient remaining qualification time")
    root = OUTPUT / args.cohort
    root.mkdir(exist_ok=False)
    started = datetime.now(UTC).isoformat()
    with (root / "qualification.log").open("x", encoding="utf-8") as log:
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--cohort", args.cohort, "--child"],
                stdout=log,
                stderr=log,
                timeout=min(900, remaining),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            result = dict(exit_code=process.returncode)
        except subprocess.TimeoutExpired:
            result = dict(terminated=True, reason="independent hard cutoff")
    primary.save(
        root / "supervisor.json",
        dict(started=started, ended=datetime.now(UTC).isoformat(), **result),
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
