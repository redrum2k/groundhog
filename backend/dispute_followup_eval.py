"""Offline qualification runner. Expected outcomes never enter application/model input."""

import hashlib
import json
import sys
from pathlib import Path

from app.data_products import build_package
from app.orders.service import DomainError as BaseDomainError
from app.runtime.broker import Broker
from app.runtime.dispute_assessment import DisputeAssessor
from app.runtime.jobflow import Jobflow
from app.storage.jobflow import DomainError, canonical
from dispute_followup_access import OUTPUT, configured_window
from tests.broker.conftest import ACTORS, Clock, accept_order, command, parameters, source_bytes

# Frozen independent reviewer suite, not generated from candidate output.
CASES = (
    (
        "J1",
        "The delivered JSON reports 48,250 for Harbor "
        "even though the accepted source reports 84,250.",
        "justified",
        True,
    ),
    (
        "J2",
        "Your downloadable household-income figure has the digits transposed. "
        "Please reconcile it with the agreed source. "
        "I like the blue cover and our finance team meets on Tuesdays.",
        "justified",
        True,
    ),
    (
        "N1",
        "The observation is older than the twenty-one-day limit we agreed.",
        "not_justified",
        False,
    ),
    (
        "N2",
        "You sent stale observations: the measurement is outside our agreed age window. "
        "Our director strongly dislikes the report font.",
        "not_justified",
        False,
    ),
    (
        "U1",
        "The chart does not satisfy the premium visual quality we agreed verbally.",
        "unclear",
        False,
    ),
    (
        "U2",
        "This presentation is not executive-ready as promised in our conversation. "
        "Your source revision and household-income number look accurate.",
        "unclear",
        False,
    ),
)


def source_hash():
    root = Path(__file__).parent
    entries = [
        (p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted((root / "app").rglob("*.py"))
    ]
    entries.append(("uv.lock", hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()))
    return hashlib.sha256(canonical(entries).encode()).hexdigest()


def corrupt(spec, sources):
    result = build_package(spec, sources)
    name, media, raw = result[0]
    parsed = json.loads(raw)
    parsed["rows"][0]["value"] = 48250
    result[0] = name, media, canonical(parsed).encode()
    return result


def evaluate(label, complaint, expected, broken, *, model, frozen_hash):
    arm = "candidate" if model else "rules"
    target = OUTPUT / f"{label}-{arm}"
    if (target / "result.json").exists():
        return json.loads((target / "result.json").read_text(encoding="utf-8"))
    if target.exists():
        # Preserve an interrupted trial. Do not recreate orders or repeat a call.
        import sqlite3

        with sqlite3.connect(target / "orders.sqlite3") as db:
            body = json.loads(db.execute("SELECT body FROM br_orders").fetchone()[0])
            count = db.execute("SELECT count(*) FROM br_assessment_attempts").fetchone()[0]
        state = body["base_order"]["order"]
        result = {
            "case": label,
            "arm": arm,
            "expected": expected,
            "order_id": body["id"],
            "source_hash": frozen_hash,
            "status": "BLOCKED",
            "first_attempt": True,
            "reason": "Interrupted qualification retained; no redispatch",
            "attempts_retained": count,
            "state": state["order_state"],
            "free_corrections_used": state["free_regenerations_used"],
        }
        if state["regeneration_pending"] and count == 0:
            result["reason"] = (
                "Existing public dispute eligibility gate; original exception retained"
            )
        (target / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        return result
    target.mkdir(exist_ok=False)  # no silent retries or overwriting failed trials
    broker = Broker(
        Jobflow(target / "orders.sqlite3", demo=True, clock=Clock()),
        producer=corrupt if broken else build_package,
        dispute_assessment_enabled=model,
    )
    raw = source_bytes(
        source_id="harbor-statistics",
        geography="Harbor District",
        boundary_version="2026-H2",
        rows=[
            dict(
                entity_id="harbor-017",
                region_id="H017",
                value=84250,
                observed_at="2026-10-15T00:00:00Z",
            )
        ],
    )
    params = parameters(
        geography="Harbor District",
        boundary_version="2026-H2",
        region_ids=["H017"],
        coverage_ids=["harbor-017"],
        max_age_days=21,
    )
    record = accept_order(broker, raw=raw, params=params)
    record = command(broker, record, "provider", "produce")
    result = {
        "case": label,
        "arm": arm,
        "expected": expected,
        "order_id": record.id,
        "source_hash": frozen_hash,
        "first_attempt": True,
        "simulated_clock": True,
    }
    assessor = None
    try:
        record = command(broker, record, "customer", "dispute", text=complaint)
        if source_hash() != frozen_hash:
            raise RuntimeError("Candidate source changed after freeze")
        if model:
            assessor = DisputeAssessor(final_evaluation=True)
            broker.dispute_assessor = assessor
        command(broker, record, "investigator", "investigate")
        current = broker.view(ACTORS["customer"], record.id)
        events = broker.events(ACTORS["customer"], record.id)
        assessment = [event["payload"] for event in events if event["type"] == "dispute.assessed"]
        if assessment:
            event = assessment[-1]
            result.update(
                effective=event["kind"],
                raw=event["raw_candidate"],
                validation=event["validation"],
                decided_by=event["decided_by"],
                event=event,
            )
        else:
            effective = "not_justified" if current.resolution == "NO_REMEDY" else "unclear"
            result.update(effective=effective, decided_by="rules")
        result["status"] = "PASS" if result["effective"] == expected else "FAIL"
        result["ledger_entries"] = len(current.base_order.order.ledger)
        result["payment_phase"] = current.base_order.order.payment_phase
        result["free_corrections_used"] = current.base_order.order.free_regenerations_used
        with broker.store.connect() as db:
            attempts = [dict(row) for row in db.execute("SELECT * FROM br_assessment_attempts")]
        result["attempts"] = attempts
        (target / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    except (DomainError, BaseDomainError) as error:
        result.update(
            status="BLOCKED",
            reason="Existing public dispute eligibility gate",
            error_type=type(error).__name__,
            state=record.base_order.order.order_state,
            free_corrections_used=record.base_order.order.free_regenerations_used,
        )
    finally:
        if assessor:
            assessor.close()
    (target / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("case", "arm", "status", "effective", "decided_by")
                if k in result
            }
        ),
        flush=True,
    )
    return result


def main():
    global OUTPUT
    if "--technical-cohort-2" in sys.argv:
        # Explicit new cohort; keep every first-cohort failure and database intact.
        OUTPUT = OUTPUT / "technical-cohort-2"
        OUTPUT.mkdir(exist_ok=False)
    budget = configured_window()
    plan = Path(__file__).parent.parent / "DISPUTE_ACCEPTANCE_PLAN.md"
    plan_hash = hashlib.sha256(plan.read_bytes()).hexdigest()
    frozen_hash = source_hash()
    freeze = {
        "plan_sha256": plan_hash,
        "source_hash": frozen_hash,
        "before": budget.summary(),
        "suite": CASES,
    }

    def save_here(name, value):
        with (OUTPUT / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)

    if (OUTPUT / "evaluation-freeze.json").exists():
        if "--resume-technical" not in sys.argv:
            raise RuntimeError("Existing evaluation requires explicit technical resume, not rerun")
        save_here("evaluation-technical-resume.json", freeze)
    else:
        save_here("evaluation-freeze.json", freeze)
    budget.allocate_final(
        10,
        plan_sha256=plan_hash,
        reason="Frozen six-case follow-up; retain $10 above < $4 four-call forecast",
    )
    results = []
    for case in CASES:
        for model in (False, True):
            results.append(evaluate(*case, model=model, frozen_hash=frozen_hash))
    save_here(
        "evaluation-results.json",
        {
            "source_hash": frozen_hash,
            "plan_sha256": plan_hash,
            "results": results,
            "after": budget.summary(),
            "feature_enabled_by_default": False,
        },
    )
    print(json.dumps(budget.summary(), indent=2))


if __name__ == "__main__":
    main()
