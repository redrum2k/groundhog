"""Fresh primary HTTP qualification. Labels stay in this harness, never model inputs.

The parent bounds the child independently of the chat/terminal. Both enforce the
registered deadline; existing SDK ledger guards every paid dispatch. No rerolls.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.agents.compiler import OfflineCompiler
from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import AcceptQuoteCommand, Complaint, DisputeCommand, QuoteRequest
from app.contracts.payments import FundingAuthorization
from app.contracts.runs import RunCreate
from app.datasets import canonical
from app.investigation.dataset import semantic_attempt
from app.main import create_app
from app.runtime.catalog_worker import CatalogWorker
from primary_followup_access import CUTOFF, OUTPUT, configured_window
from tests.dataset.conftest import command

CASES = (
    dict(
        id="P1",
        expanded=True,
        text="Standalone yoga is covered by our agreed fitness scope.",
        expected="PASS",
        basis="Explicit accepted expanded category plus source category.",
    ),
    dict(
        id="P2",
        expanded=False,
        text="Yoga studios belong in our accepted fitness definition.",
        expected="FAIL",
        basis="Explicit accepted standalone-yoga exclusion, matching verified category.",
    ),
    dict(
        id="P3",
        expanded=False,
        text="Yoga isn't included in the agreed gym/app definition.",
        expected="PASS",
        basis="Negative scope claim is true under explicit accepted exclusion; no output fault.",
    ),
    dict(
        id="P4",
        expanded=False,
        text="You left ZIP 94110 out of the delivered CSV.",
        field="coverage",
        product="94110",
        expected="FAIL",
        basis="94110 independently present in frozen coverage, source and actual delivered CSV.",
    ),
    dict(
        id="P5",
        expanded=False,
        text="The fitness category was promised to be executive-ready.",
        expected="UNKNOWN",
        basis="No accepted contractual quality metric or authority establishes executive-ready.",
    ),
    dict(
        id="P6",
        expanded=False,
        text="Under our accepted scope, standalone yoga counts as gym membership.",
        taxonomy=None,
        expected="UNKNOWN",
        basis="Registered frozen authority does not establish yoga_is_gym; no invented entailment.",
    ),
)


def source_hash():
    root = Path(__file__).parent
    entries = [
        (p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted((root / "app").rglob("*.py"))
    ]
    entries.append(("uv.lock", hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()))
    return hashlib.sha256(canonical(entries)).hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def post(client, path, payload, key=None):
    response = client.post(path, json=payload, headers={"Idempotency-Key": key} if key else {})
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Qualification HTTP boundary {path}: {response.status_code}")
    return response.json()


def evaluate(recipe):
    target = OUTPUT / recipe["id"]
    target.mkdir(exist_ok=False)
    app = create_app(
        target / "orders.sqlite3",
        artifact_root=target / "artifacts",
        run_worker=False,
        compiler=OfflineCompiler(),
        payment_mode="mock",
    )
    with TestClient(app) as client:
        service = app.state.orders
        if "taxonomy" in recipe:
            seeded = post(client, "/runs", RunCreate().model_dump(mode="json"), "seed")
            assert CatalogWorker(service).run_once()  # drain legitimate seed compilation
            source = next(
                s
                for s in service.registry.manifest("sf-aggregate-v1")
                if s.source_id.endswith(":authority")
            )
            data = json.loads(service.store.read(source.artifact))
            data.update(version=2, yoga_is_gym=recipe["taxonomy"])
            service.registry.register(
                source.model_copy(
                    update={
                        "version": 2,
                        "artifact": service.store.put(canonical(data), "application/json"),
                    }
                )
            )
            assert seeded["id"]
        prompt = "SF adults 25-34, gym membership or fitness app users. " + (
            "Include yoga." if recipe["expanded"] else "Exclude yoga."
        )
        run = post(client, "/runs", RunCreate(prompt=prompt).model_dump(mode="json"), "create")[
            "id"
        ]
        assert CatalogWorker(service).run_once()
        draft = service.get_request(run)
        quote = post(
            client,
            f"/requests/{run}/quotes",
            QuoteRequest(expected_revision=draft.revision, idempotency_key="quote").model_dump(
                mode="json"
            ),
        )
        view = post(
            client,
            "/quote-acceptance",
            AcceptQuoteCommand(
                quote_id=quote["quote_id"], customer_actor="AcmeFitness", idempotency_key="accept"
            ).model_dump(mode="json"),
        )
        order_id = view["order"]["snapshot"]["order_id"]
        order = service.get(order_id)
        prep = post(
            client,
            f"/orders/{order_id}/funding-preparation",
            command(order, "prepare").model_dump(mode="json"),
        )
        funding = FundingAuthorization(
            **command(order, "fund").model_dump(),
            funding_attempt_id=prep["funding_attempt_id"],
            payment_hash=prep["terms"]["payment_hash"],
            simulate=True,
        )
        post(client, f"/orders/{order_id}/funding-authorizations", funding.model_dump(mode="json"))
        service.payments.work()
        assert CatalogWorker(service).run_once()
        order = service.get(order_id)
        if not order.deliveries:
            raise RuntimeError(
                "Production did not publish; semantic dispute legitimately ineligible"
            )
        assert order.verification.passed and not order.verification.provider_defect
        original = order.snapshot
        field = recipe.get("field", "category")
        complaint = DisputeCommand(
            **command(order, "dispute").model_dump(),
            complaint=Complaint(
                artifact_id=order.deliveries[-1].csv.artifact_id,
                requirement_id="R-" + field.upper(),
                product_id=recipe.get("product", "dataset"),
                field=field,
                text=recipe["text"],
                intent="dispute_fact",
            ),
        )
        response = post(client, f"/orders/{order_id}/disputes", complaint.model_dump(mode="json"))
        dispatched = service.get(order_id)
        gateway = ClaudeGateway(enabled=True)
        service.investigator = SimpleNamespace(assessor=gateway)
        try:
            assert CatalogWorker(service).run_once()
        finally:
            gateway.client.close()
        current = service.get(order_id)
        with service.repository.transaction() as db:
            attempt = semantic_attempt(db, dispatched)
        if attempt is None:
            raise RuntimeError("No durable primary semantic attempt")
        page = client.get(f"/runs/{run}/events").json()
        verdicts = [e["verdict"] for e in page["events"] if e["type"] == "verdict"]
        citations = []
        for verdict in verdicts:
            for evidence_id in verdict["evidenceIds"]:
                resolved = client.get(f"/runs/{run}/evidence/{evidence_id}")
                assert resolved.status_code == 200
                citations.append(resolved.json())
        for _ in range(3):
            assert client.get(f"/runs/{run}/events").json()["events"] == page["events"]
        assert (
            post(client, f"/orders/{order_id}/disputes", complaint.model_dump(mode="json"))
            == response
        )
        assert not CatalogWorker(service).run_once()
        assert (
            current.snapshot == original
            and current.cases[-1].deadline == dispatched.cases[-1].deadline
        )
        assert not current.ledger and not current.free_corrections_used
        assert current.authorization.status == "mock_authorized"
        for ref in attempt.effective.citations:
            service.store.resolve(ref, current.artifacts)
        save(target / "attempt.json", attempt.model_dump(mode="json"))
        save(target / "order.json", current.model_dump(mode="json"))
        save(target / "events.json", page)
        save(target / "resolved-evidence.json", citations)
        raw = attempt.raw_response or {}
        result = dict(
            case=recipe["id"],
            expected=recipe["expected"],
            raw=attempt.candidate.result if attempt.candidate else None,
            effective=attempt.effective.result,
            status=attempt.status,
            failure=attempt.failure,
            actual_model=raw.get("model"),
            usage=raw.get("usage"),
            latency_seconds=attempt.elapsed_seconds,
            model_correct=bool(
                attempt.candidate and attempt.candidate.result == recipe["expected"]
            ),
            effective_correct=attempt.effective.result == recipe["expected"],
            verdict=verdicts[-1] if verdicts else None,
            no_financial_effects=True,
            citations_resolved=len(citations),
        )
        save(target / "result.json", result)
        print(json.dumps({k: v for k, v in result.items() if k != "verdict"}), flush=True)
        return result


def child():
    budget = configured_window()
    plan = dict(
        cases=CASES,
        source_sha256=source_hash(),
        model=os.environ["CLAUDE_MODEL"],
        deadline=CUTOFF,
        max_output_tokens=4096,
        timeout_seconds=20,
        retries=0,
        acceptance=(
            "Raw and effective labels reported separately. No model-only remedy. "
            "UI not qualified; flag OFF."
        ),
        pricing_url="https://platform.claude.com/docs/en/about-claude/pricing",
        input_usd_per_million=4,
        output_usd_per_million=20,
    )
    save(OUTPUT / "frozen-plan.json", plan)
    budget.allocate_final(
        10,
        plan_sha256=hashlib.sha256(canonical(plan)).hexdigest(),
        reason=(
            f"{len(CASES)} fresh primary cases; measured semantic cost under $0.10/call. "
            "Keep $10 holdback; no budget reset."
        ),
    )
    before = budget.summary()
    os.environ["ENABLE_DATASET_MODEL_ASSESSMENT"] = "true"
    results = []
    for recipe in CASES:
        if datetime.now(UTC) >= datetime.fromisoformat(CUTOFF):
            break
        try:
            results.append(evaluate(recipe))
        except Exception as error:
            failed = dict(
                case=recipe["id"],
                failure=type(error).__name__,
                expected=recipe["expected"],
                status="HARNESS_OR_RUNTIME_FAILURE",
            )
            save(OUTPUT / (recipe["id"] + "-failure.json"), failed)
            print(json.dumps(failed), flush=True)
            results.append(failed)
    save(
        OUTPUT / "results.json",
        dict(before=before, after=budget.summary(), cases=results, source_sha256=source_hash()),
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if "--child" in sys.argv:
        child()
        return
    if (OUTPUT / "supervisor.json").exists() or (OUTPUT / "frozen-plan.json").exists():
        raise RuntimeError("Qualification already attempted; no implicit rerun")
    remaining = (datetime.fromisoformat(CUTOFF) - datetime.now(UTC)).total_seconds()
    if remaining < 180:
        raise RuntimeError("Insufficient authorized time for this frozen cohort")
    started = datetime.now(UTC).isoformat()
    with (OUTPUT / "qualification.log").open("x", encoding="utf-8") as log:
        try:
            process = subprocess.run(
                [sys.executable, str(Path(sys.argv[0]).resolve()), "--child"],
                stdout=log,
                stderr=log,
                timeout=min(300, remaining),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            result = dict(exit_code=process.returncode)
        except subprocess.TimeoutExpired:
            result = dict(terminated=True, reason="independent hard timeout")
    save(
        OUTPUT / "supervisor.json",
        dict(started=started, ended=datetime.now(UTC).isoformat(), **result),
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
