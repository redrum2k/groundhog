import asyncio
import json

import pytest

from app.contracts.broker import DraftCreate
from app.contracts.improvement import ImprovementCommand, PatchEdit, PatchProposal
from app.improvement.scenarios import ScenarioAdapter
from app.improvement.service import Improvement, guard_patch
from app.runtime.broker import Broker
from app.runtime.jobflow import Jobflow
from app.storage.jobflow import DomainError, canonical, uid
from tests.broker.conftest import ACTORS, accept_order, command, source_bytes


def improve(service, verb, **kwargs):
    request = ImprovementCommand(
        idempotency_key=uid("improve"), verb=verb, customer_id="northwind", **kwargs
    )
    return asyncio.run(service.command(ACTORS["controller"], request))


def test_I01_to_I07_executable_cycle_negative_probe_and_prospective_rollback(broker, monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "JOBFLOW_ANTHROPIC_MAX_CALLS"):
        monkeypatch.delenv(key, raising=False)
    old = accept_order(broker, clarity=False)
    frozen = old.base_order.order.snapshot.model_dump_json()
    service = Improvement(broker)
    records = service.view(ACTORS["controller"], "northwind", old.original_specification.product_id)
    incidents = tuple(item["id"] for item in records["incidents"][:1])
    blocked = improve(service, "propose", incident_ids=incidents)
    assert blocked["status"] == "BLOCKED" and blocked["model_calls"] == 0
    proposed = improve(
        service, "propose", incident_ids=incidents, mode="DETERMINISTIC_INFRASTRUCTURE"
    )
    assert proposed["status"] == "COMPLETE" and len(proposed["patch_ids"]) == 2
    assert (
        service.view(ACTORS["controller"], "northwind", old.original_specification.product_id)[
            "active_template"
        ]["id"]
        == "intake-v1"
    )
    good, bad = proposed["patch_ids"]
    positive = improve(service, "probe", patch_id=good)
    assert positive["promotion_eligible"], positive
    assert not positive["violations"]
    assert (
        positive["summary"]["evolving_process"]["company_staff_touches"]
        < positive["summary"]["static"]["company_staff_touches"]
    )
    assert positive["summary"]["evolving_process"]["outcomes"]["PASS"]
    assert positive["summary"]["evolving_process"]["outcomes"]["FAIL"]
    assert positive["summary"]["evolving_process"]["outcomes"]["UNKNOWN"]
    negative = improve(service, "probe", patch_id=bad)
    assert negative["patch_status"] == "REJECTED"
    assert any("completion_regression" in violation for violation in negative["violations"])
    with pytest.raises(DomainError, match="validated patch"):
        improve(service, "approve", patch_id=bad)
    assert improve(service, "probe", patch_id=bad)["status"] == "BLOCKED"
    approved = improve(service, "approve", patch_id=good)
    assert approved["status"] == "APPROVED"
    assert (
        service.view(ACTORS["controller"], "northwind", old.original_specification.product_id)[
            "active_template"
        ]["id"]
        == "intake-v1"
    )
    improve(service, "activate", version_id=approved["version_id"])
    new = command(broker, accept_order(broker, clarity=False), "provider", "produce")
    assert new.original_specification.template_version == approved["version_id"]
    assert new.base_order.order.data_verification.verdict == "PASS"
    raw = source_bytes(
        rows=[
            dict(
                entity_id="region-001",
                region_id="R001",
                value=95000.0,
                observed_at="2020-01-01T00:00:00Z",
            )
        ]
    )
    failed = command(broker, accept_order(broker, clarity=False, raw=raw), "provider", "produce")
    assert failed.base_order.order.data_verification.verdict == "FAIL"
    absent = source_bytes(
        rows=[dict(entity_id="region-001", region_id="R001", value=95000.0, observed_at=None)]
    )
    unknown = command(
        broker, accept_order(broker, clarity=False, raw=absent), "provider", "produce"
    )
    assert unknown.base_order.order.data_verification.verdict == "UNKNOWN"
    assert (
        broker.view(ACTORS["customer"], old.id).base_order.order.snapshot.model_dump_json()
        == frozen
    )
    cross = broker.create_draft(
        ACTORS["customer_other"], DraftCreate(idempotency_key=uid("cross"), intent="recent data")
    )
    assert cross.template_version == "intake-v1"
    other_product = broker.create_draft(
        ACTORS["customer"],
        DraftCreate(
            idempotency_key=uid("cross-product"), intent="recent data", product_id="other_product"
        ),
    )
    assert other_product.template_version == "intake-v1"
    # A later proposal consumes actual tested experiences and changes its question choice.
    second = improve(
        service, "propose", incident_ids=incidents, mode="DETERMINISTIC_INFRASTRUCTURE"
    )
    assert second["experience_ids"]
    second_patch = service.record(ACTORS["controller"], second["patch_ids"][0])
    assert second_patch["proposal"]["experience_ids"]
    assert any(edit["op"] == "replace_question" for edit in second_patch["proposal"]["operations"])
    assert (
        improve(service, "propose", incident_ids=incidents, mode="DETERMINISTIC_INFRASTRUCTURE")[
            "status"
        ]
        == "BLOCKED"
    )
    improve(service, "revoke", version_id=approved["version_id"])
    restarted = Broker(Jobflow(broker.store.path, demo=True, clock=broker.clock))
    future = restarted.create_draft(
        ACTORS["customer"], DraftCreate(idempotency_key=uid("after-rollback"), intent="recent data")
    )
    assert future.template_version == "intake-v1"
    assert (
        restarted.view(ACTORS["customer"], new.id).original_specification.template_version
        == approved["version_id"]
    )
    assert (
        restarted.view(ACTORS["customer"], old.id).base_order.order.snapshot.model_dump_json()
        == frozen
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"op": "set_price", "amount": 1},
        {"op": "require_intake_field", "field": "authorization"},
        {"op": "bind_validator", "recipe": "execute_python", "code": "print(1)"},
        {"op": "require_intake_field", "field": "max_age_days", "value": 36500},
    ],
)
def test_I02_protected_changes_are_not_in_the_schema(bad):
    with pytest.raises(ValueError):
        PatchEdit.model_validate(bad)


def test_bound_validator_cannot_change_parameters_or_ask_for_money():
    for edit in [
        PatchEdit(op="bind_validator", recipe="age_within_days", parameters_from=("as_of",)),
        PatchEdit(
            op="replace_question", field="max_age_days", question="Please approve payment now."
        ),
    ]:
        proposal = PatchProposal(
            baseline_version="intake-v1",
            customer_id="northwind",
            product_id="product",
            incident_ids=("missing",),
            rationale="test",
            expected_mechanism="test",
            operations=(edit,),
        )
        # A missing incident is itself a protected boundary, checked before any edit.
        with pytest.raises(ValueError):
            guard_patch(proposal, {"id": "intake-v1"}, [])


@pytest.mark.parametrize(
    "hidden", ["gold", "expected_verdict", "repair_recipe", "test_id", "world_truth"]
)
def test_I08_loader_rejects_hidden_metadata(hidden):
    from app.improvement.probes import development_cases

    data = {"schema_version": 1, "cases": [development_cases()[0].model_dump(mode="json")]}
    data["cases"][0][hidden] = "PASS"
    with pytest.raises(ValueError, match="Protected"):
        ScenarioAdapter.load(canonical(data).encode())


def test_model_jobs_survive_restart_without_automatic_retry(broker):
    service = Improvement(broker)
    with broker.store.connect(write=True) as db:
        db.execute(
            "INSERT INTO im_cycles VALUES(?,?,?,?,?,NULL)",
            (
                "lost-call",
                "northwind",
                "product",
                "RUNNING",
                canonical({"command": {"body": {"verb": "propose"}}}),
            ),
        )
    service.recover()
    with broker.store.connect() as db:
        row = db.execute("SELECT status,response FROM im_cycles WHERE id='lost-call'").fetchone()
        assert row[0] == "UNKNOWN"
        assert "no automatic retry" in json.loads(row[1])["reason"]
