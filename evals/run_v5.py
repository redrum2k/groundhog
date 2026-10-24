"""Offline finite acceptance/demo runner. Gold is loaded only after candidate selection."""

import argparse
import asyncio
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cases.v5_transfer import transfer_cases

from app.contracts.broker import BrokerCommand, DraftCreate, IntakeDraft, SourceUpload
from app.contracts.improvement import ImprovementCommand
from app.contracts.models import Money
from app.improvement.probes import development_cases, implementation_digest, run_probe
from app.improvement.scenarios import ConstrainedCustomer, ScenarioAdapter, ScenarioClock
from app.improvement.service import Improvement
from app.runtime.broker import Broker
from app.runtime.jobflow import DEMO_ACTORS, Jobflow
from app.storage import broker as storage
from app.storage.jobflow import canonical, digest, uid

ACTORS = {actor.id: actor for actor in DEMO_ACTORS}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def new_draft(broker, case):
    draft = broker.create_draft(
        ACTORS["customer"],
        DraftCreate(idempotency_key=uid("draft"), intent=case.intent, product_id=case.product_id),
    )
    for source in case.sources:
        draft = broker.upload(
            ACTORS["provider"],
            draft.id,
            SourceUpload(
                idempotency_key=uid("source"),
                expected_revision=draft.revision,
                filename=source.filename,
                content_base64=source.content_base64,
            ),
        )
    return draft


def complete_intake(broker, case):
    draft = new_draft(broker, case)
    customer = ConstrainedCustomer(case)
    for question in tuple(draft.questions):
        value = customer.answer(question)
        if value is None:
            raise ValueError("Fixture did not answer the actual requested clarification")
        draft = broker.draft_command(
            ACTORS["customer"],
            draft.id,
            BrokerCommand(
                idempotency_key=uid("answer"),
                expected_revision=draft.revision,
                verb="answer_intake",
                question_id=question.id,
                value=value,
            ),
        )
    if draft.unresolved_fields:
        raise ValueError("Activated template did not collect the complete agreed specification")
    draft = broker.draft_command(
        ACTORS["provider"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("offer"),
            expected_revision=draft.revision,
            verb="offer",
            capability="SUPPORTED",
            price=Money(amount_minor=1000, currency="USDSIM", decimals=2),
        ),
    )
    draft = broker.draft_command(
        ACTORS["customer"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("accept"),
            expected_revision=draft.revision,
            verb="accept_specification",
            digest=draft.acceptance_digest,
            authorization_expires_at=broker.clock() + timedelta(hours=1),
        ),
    )
    record = broker.view(ACTORS["customer"], draft.id)
    return broker.command(
        ACTORS["provider"],
        record.id,
        BrokerCommand(
            idempotency_key=uid("produce"), expected_revision=record.revision, verb="produce"
        ),
    )


async def run(output):
    output.mkdir(parents=True, exist_ok=False)
    clock = ScenarioClock(datetime.now(UTC))
    broker = Broker(Jobflow(output / "workflow.sqlite3", demo=True, clock=clock))
    service = Improvement(broker)
    development = development_cases()
    historical = development[4]
    draft = new_draft(broker, historical)
    with broker.store.connect(write=True) as db:
        draft = storage.get(db, "br_drafts", draft.id, IntakeDraft)
        draft.specification = historical.historical_specification
        draft.offered_price = Money(amount_minor=1000, currency="USDSIM", decimals=2)
        draft.provider_actor_id = "provider"
        draft.acceptance_digest = digest(draft.specification.model_dump(mode="json"))
        broker._accept_draft(
            db,
            draft,
            ACTORS["customer"],
            BrokerCommand(
                idempotency_key=uid("historical"),
                expected_revision=draft.revision,
                verb="accept_specification",
                digest=draft.acceptance_digest,
                authorization_expires_at=clock() + timedelta(hours=1),
            ),
            historical_import=True,
        )
        storage.save(db, "br_drafts", draft)
    old = broker.view(ACTORS["customer"], draft.id)
    old = broker.command(
        ACTORS["provider"],
        old.id,
        BrokerCommand(
            idempotency_key=uid("produce-old"), expected_revision=old.revision, verb="produce"
        ),
    )
    old_snapshot = old.base_order.order.snapshot.model_dump_json()
    clock.now += timedelta(seconds=600)
    old = broker.view(ACTORS["customer"], old.id)
    records = service.view(ACTORS["controller"], "northwind", historical.product_id)
    incident = next(
        item
        for item in reversed(records["incidents"])
        if item["entity_id"] == old.id and item["cause"] == "MISSING_SPECIFICATION"
    )
    model_status = "NOT_RUN"
    if not records["model_available"]:
        blocked = await service.command(
            ACTORS["controller"],
            ImprovementCommand(
                idempotency_key=uid("model-status"),
                verb="propose",
                customer_id="northwind",
                incident_ids=(incident["id"],),
            ),
        )
        model_status = blocked["status"]
        write_json(output / "model-status.json", blocked)
    proposed = await service.command(
        ACTORS["controller"],
        ImprovementCommand(
            idempotency_key=uid("propose"),
            verb="propose",
            customer_id="northwind",
            incident_ids=(incident["id"],),
            mode="DETERMINISTIC_INFRASTRUCTURE",
        ),
    )
    write_json(output / "proposal-job.json", proposed)
    probes = []
    for patch_id in proposed["patch_ids"]:
        result = await service.command(
            ACTORS["controller"],
            ImprovementCommand(
                idempotency_key=uid("probe"),
                verb="probe",
                customer_id="northwind",
                patch_id=patch_id,
            ),
        )
        if result["status"] != "COMPLETE":
            raise ValueError(f"Probe failed: {result}")
        report = service.record(ACTORS["controller"], result["probe_id"])
        write_json(output / "probes" / f"{report['id']}.json", report)
        probes.append(report)
    selected = next((report for report in probes if report["promotion_eligible"]), None)
    if selected is None:
        write_json(
            output / "result.json",
            {"status": "RETAIN_BASE", "probes": probes, "real_model_status": model_status},
        )
        return 2
    approved = await service.command(
        ACTORS["controller"],
        ImprovementCommand(
            idempotency_key=uid("approve"),
            verb="approve",
            customer_id="northwind",
            patch_id=selected["patch_id"],
        ),
    )
    await service.command(
        ACTORS["controller"],
        ImprovementCommand(
            idempotency_key=uid("activate"),
            verb="activate",
            customer_id="northwind",
            version_id=approved["version_id"],
        ),
    )
    version = service.record(ACTORS["controller"], approved["version_id"])
    # Freeze the candidate before instantiating reserved inputs or revealing endpoints.
    frozen = {
        "patch_id": selected["patch_id"],
        "candidate_sha256": selected["candidate_sha256"],
        "implementation_sha256": implementation_digest(),
        "version": version,
    }
    write_json(output / "frozen-candidate.json", frozen)
    transfer = transfer_cases()
    from app.contracts.improvement import ImprovementPatch

    patch = ImprovementPatch.model_validate(
        service.record(ACTORS["controller"], selected["patch_id"])
    )
    transfer_report = run_probe(patch, version, cases=transfer)
    write_json(output / "transfer-results.json", transfer_report)
    # Only the evaluator receives endpoints; application/model inputs never contain them.
    from expected.v5_reference import reference_endpoints, score

    reference = reference_endpoints(development, transfer)
    scored = score([*selected["outcomes"], *transfer_report["outcomes"]], reference)
    write_json(output / "offline-score.json", scored)
    manifest = {
        "schema_version": 1,
        "cases": [case.model_dump(mode="json") for case in (*development, *transfer)],
    }
    ScenarioAdapter.load(canonical(manifest).encode())
    write_json(output / "scenario-inputs.json", manifest)
    split_manifest = {
        "development": [case.case_id for case in development],
        "reserved_transfer": [case.case_id for case in transfer],
        "groups": {case.case_id: "development-bay-counterfactuals" for case in development},
    }
    split_manifest["groups"].update(
        {case.case_id: f"transfer-geography-{index}" for index, case in enumerate(transfer)}
    )
    write_json(output / "scenario-manifest.json", split_manifest)
    new_orders = []
    for case in development[:3]:
        record = complete_intake(broker, case)
        if record.base_order.order.regeneration_pending:
            record = broker.command(
                ACTORS["provider"],
                record.id,
                BrokerCommand(
                    idempotency_key=uid("bounded-correction"),
                    expected_revision=record.revision,
                    verb="produce",
                ),
            )
        if record.base_order.order.data_verification.verdict == "PASS":
            before_capture = record.model_dump(mode="json")
            record = broker.command(
                ACTORS["customer"],
                record.id,
                BrokerCommand(
                    idempotency_key=uid("accept-delivery"),
                    expected_revision=record.revision,
                    verb="accept_delivery",
                ),
            )
            write_json(output / "review-before-capture.json", before_capture)
            for identifier in record.delivery_artifact_ids:
                raw, metadata, _ = broker.artifact(ACTORS["customer"], record.id, identifier)
                artifact_path = output / "artifacts" / metadata["filename"]
                artifact_path.parent.mkdir(exist_ok=True)
                artifact_path.write_bytes(raw)
        write_json(output / "orders" / f"{record.id}.json", record.model_dump(mode="json"))
        write_json(
            output / "traces" / f"{record.id}.json", broker.events(ACTORS["customer"], record.id)
        )
        new_orders.append(record)
    producer = broker.producer

    def interrupted_provider(_specification, _sources):
        raise ValueError("Simulated provider transport interruption")

    try:
        broker.producer = interrupted_provider
        red = complete_intake(broker, development[0])
    finally:
        broker.producer = producer
    assert red.colour == "red" and not red.base_order.order.deliveries
    write_json(output / "red-order.json", red.model_dump(mode="json"))
    write_json(output / "traces" / f"{red.id}.json", broker.events(ACTORS["customer"], red.id))
    new_orders.append(red)

    def wrong_value(specification, sources):
        package = producer(specification, sources)
        filename, media, raw = package[0]
        data = json.loads(raw)
        data["rows"][0]["value"] = 1
        return [(filename, media, canonical(data).encode()), *package[1:]]

    try:
        broker.producer = wrong_value
        faulty = complete_intake(broker, development[0])
    finally:
        broker.producer = producer
    assert faulty.base_order.order.regeneration_pending
    write_json(output / "correction-before.json", faulty.model_dump(mode="json"))
    corrected = broker.command(
        ACTORS["provider"],
        faulty.id,
        BrokerCommand(
            idempotency_key=uid("correct"), expected_revision=faulty.revision, verb="produce"
        ),
    )
    assert corrected.base_order.order.data_verification.verdict == "PASS"
    assert (
        faulty.base_order.order.deliveries[-1].artifacts[0].sha256
        != corrected.base_order.order.deliveries[-1].artifacts[0].sha256
    )
    corrected = broker.command(
        ACTORS["customer"],
        corrected.id,
        BrokerCommand(
            idempotency_key=uid("accept-corrected"),
            expected_revision=corrected.revision,
            verb="accept_delivery",
        ),
    )
    assert len(corrected.base_order.order.ledger) == 1
    write_json(output / "correction-after.json", corrected.model_dump(mode="json"))
    write_json(
        output / "traces" / f"{corrected.id}.json", broker.events(ACTORS["customer"], corrected.id)
    )
    new_orders.append(corrected)
    second = await service.command(
        ACTORS["controller"],
        ImprovementCommand(
            idempotency_key=uid("second-cycle"),
            verb="propose",
            customer_id="northwind",
            incident_ids=(incident["id"],),
            mode="DETERMINISTIC_INFRASTRUCTURE",
        ),
    )
    write_json(output / "second-cycle.json", second)
    rollback = await service.command(
        ACTORS["controller"],
        ImprovementCommand(
            idempotency_key=uid("revoke"),
            verb="revoke",
            customer_id="northwind",
            version_id=approved["version_id"],
        ),
    )
    restarted = Broker(Jobflow(broker.store.path, demo=True, clock=clock))
    future = restarted.create_draft(
        ACTORS["customer"],
        DraftCreate(idempotency_key=uid("rollback-check"), intent="recent regional data"),
    )
    assert future.template_version == "intake-v1"
    assert (
        restarted.view(ACTORS["customer"], old.id).base_order.order.snapshot.model_dump_json()
        == old_snapshot
    )
    assert all(
        restarted.view(ACTORS["customer"], record.id).original_specification.template_version
        == version["id"]
        for record in new_orders
    )
    write_json(
        output / "rollback.json",
        {
            **rollback,
            "new_draft_template": future.template_version,
            "old_snapshot_unchanged": True,
            "new_accepted_versions_unchanged": True,
        },
    )
    write_json(output / "historical-order.json", old.model_dump(mode="json"))
    write_json(output / "historical-trace.json", broker.events(ACTORS["customer"], old.id))
    write_json(
        output / "improvement-records.json",
        service.view(ACTORS["controller"], "northwind", historical.product_id),
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout.strip()
    result = {
        "status": "LOCAL_INFRASTRUCTURE_PASS"
        if not scored["mismatches"] and not transfer_report["violations"]
        else "FAILED",
        "real_model_status": model_status,
        "mode": "DETERMINISTIC_INFRASTRUCTURE",
        "revision": revision,
        "implementation_sha256": implementation_digest(),
        "development_worlds": len(development),
        "reserved_transfer_worlds": len(transfer),
        "selected_probe": selected["id"],
        "rejected_candidates": sum(not item["promotion_eligible"] for item in probes),
        "development_summary": selected["summary"],
        "transfer_summary": transfer_report["summary"],
        "score": scored,
        "second_cycle_experience_reused": bool(second.get("experience_ids")),
        "second_cycle_effectiveness": "NOT_QUALIFIED",
        "rollback_verified": True,
        "measured_staff_seconds": None,
        "dollar_savings": None,
        "application_model_calls": 0,
        "new_paid_spend": 0,
        "live_settlement": False,
    }
    write_json(output / "result.json", result)
    files = {
        str(path.relative_to(output)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in output.rglob("*")
        if path.is_file() and path.suffix != ".sqlite3" and not path.name.endswith(("-wal", "-shm"))
    }
    write_json(output / "manifest.json", files)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "real_model_status",
                    "development_worlds",
                    "reserved_transfer_worlds",
                    "rollback_verified",
                )
            }
        )
    )
    return 0 if result["status"] == "LOCAL_INFRASTRUCTURE_PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(run(arguments.output.resolve())))
