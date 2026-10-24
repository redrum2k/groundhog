import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts.catalog_improvement import CatalogImprovementCommand, CatalogPatchProposal
from app.improvement.catalog import BASE, CatalogProcedures
from app.main import create_app
from app.orders.catalog import CatalogService
from app.orders.service import DomainError
from app.storage.catalog import CatalogRepository
from tests.catalog.fixtures import accepted, cmd

WORKER = "provider:local-worker"
REVIEWER = "reviewer:local-trusted"


class InjectedGateway:
    model = "injected-transport-not-real-model"
    test_double = True
    last_response = None

    def parse(self, schema, instruction, context):
        raw = {
            "candidates": [
                {
                    "corpus_id": context["corpus_id"],
                    "baseline_version": context["baseline_version"],
                    "incident_ids": [context["incidents"][0]["id"]],
                    "rationale": "An observed unreadable source led to a manual evidence request.",
                    "expected_mechanism": (
                        "Retrieve a registered same-edition corroboration before asking staff."
                    ),
                    "operations": [
                        {
                            "op": "retrieve_registered_same_edition",
                            "trigger": "REQUIRED_VALUE_UNREADABLE",
                        }
                    ],
                }
            ]
        }
        self.last_response = {"mode": "ANTHROPIC_TEST_DOUBLE", "content": raw}
        return schema.model_validate(raw)


def request(verb, key=None, **kwargs):
    return CatalogImprovementCommand(
        verb=verb,
        idempotency_key=key or verb,
        corpus_id="storage-2026",
        expected_active_version=BASE,
        reason="Explicit synthetic reviewer/test command",
        **kwargs,
    )


def proposed(setup):
    service, clock, fixtures = setup
    adapter = CatalogProcedures(service, gateway_factory=InjectedGateway)
    old = service.run_one(accepted(service, key="incident-order").snapshot.order_id)
    incident = next(r for r in adapter.view("storage-2026").records if r.kind == "catalog_incident")
    command = request("propose", incident_ids=(incident.id,))
    generated = adapter.propose(command, actor=WORKER)
    assert generated.status == "COMPLETE" and generated.mode == "ANTHROPIC_TEST_DOUBLE"
    assert adapter.propose(command, actor=WORKER) == generated
    return service, clock, fixtures, adapter, old, generated.patch_ids[0]


def test_complete_catalog_probe_activation_new_order_and_revoke_restart(setup):
    service, clock, fixtures, adapter, old, patch_id = proposed(setup)
    probe = adapter.probe(request("probe", patch_id=patch_id), actor=WORKER)
    assert probe.status == "COMPLETE" and probe.reason == "RETAIN_TESTED_CANDIDATE"
    probe_record = next(r for r in adapter.view("storage-2026").records if r.id == probe.probe_id)
    assert len(probe_record.data["report"]["outcomes"]) == 6
    assert probe_record.data["report"]["violations"] == []
    transition = {"patch_id": patch_id, "probe_id": probe.probe_id}
    with pytest.raises(DomainError, match="approval"):
        adapter.transition(request("activate", "early", **transition), actor=REVIEWER)
    with pytest.raises(DomainError, match="reviewer"):
        adapter.transition(request("approve", **transition), actor=WORKER)
    assert adapter.transition(request("approve", **transition), actor=REVIEWER).status == "APPROVED"
    activation = adapter.transition(request("activate", **transition), actor=REVIEWER)
    assert activation.status == "ACTIVE"
    # Original accepted order stays on its original procedure and terms.
    assert service.get(old.snapshot.order_id).snapshot == old.snapshot
    assert adapter.maybe_acquire(old).amendments == ()
    fresh = accepted(service, key="new-order")
    snapshot = fresh.snapshot
    fresh = service.run_one(fresh.snapshot.order_id)
    assert fresh.amendments[-1].actor == "system:registered-evidence-acquisition"
    fresh = service.run_one(fresh.snapshot.order_id)
    fresh = service.run_one(fresh.snapshot.order_id)
    assert fresh.order_state == "delivered" and fresh.verification.passed and not fresh.ledger
    fresh = service.mutate(fresh.snapshot.order_id, "accept", cmd(fresh, "accept-current"))
    assert len(fresh.ledger) == 1 and fresh.snapshot == snapshot
    revoke = request("revoke", version_id=activation.version_id).model_copy(
        update={"expected_active_version": activation.version_id}
    )
    assert adapter.transition(revoke, actor=REVIEWER).status == "REVOKED"
    restarted_service = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    restarted = CatalogProcedures(restarted_service)
    assert restarted.view("storage-2026").active_version == BASE
    with restarted.store.connect() as db:
        assert restarted.pinned(db, fresh.snapshot.order_id) == activation.version_id
    later = accepted(restarted_service, key="after-revocation")
    restarted_service.auto_mock_funding = True
    with restarted.store.connect() as db:
        assert restarted.pinned(db, later.snapshot.order_id) == BASE


def test_active_procedure_cannot_execute_after_approved_source_changes(setup, monkeypatch):
    service, _, _, adapter, _, patch_id = proposed(setup)
    probe = adapter.probe(request("probe", patch_id=patch_id), actor=WORKER)
    fields = {"patch_id": patch_id, "probe_id": probe.probe_id}
    adapter.transition(request("approve", **fields), actor=REVIEWER)
    adapter.transition(request("activate", **fields), actor=REVIEWER)
    fresh = accepted(service, key="source-change-order")
    monkeypatch.setattr("app.improvement.catalog.implementation_digest", lambda: "changed-source")
    fresh = service.run_one(fresh.snapshot.order_id)
    assert fresh.order_state == "waiting_evidence"
    assert fresh.amendments == ()


def test_protected_edits_cannot_enter_typed_surface():
    base = dict(
        corpus_id="c",
        baseline_version=BASE,
        incident_ids=("i",),
        rationale="test",
        expected_mechanism="test",
    )
    for operation in (
        "set_price",
        "capture",
        "change_accepted_terms",
        "remove_validator",
        "set_source_truth",
        "grant_role",
        "edit_history",
        "deploy",
    ):
        with pytest.raises(ValidationError):
            CatalogPatchProposal(
                **base, operations=[{"op": operation, "trigger": "REQUIRED_VALUE_UNREADABLE"}]
            )


def test_source_change_invalidates_approval_and_command_replays_are_exact(setup, monkeypatch):
    _, _, _, adapter, _, patch_id = proposed(setup)
    # Injected test runner explicitly tests the approval binding, not quality.
    adapter.probe_runner = lambda _: {"promotion_eligible": True, "selection": "TEST_DOUBLE"}
    probe = adapter.probe(request("probe", patch_id=patch_id), actor=WORKER)
    approve = request("approve", patch_id=patch_id, probe_id=probe.probe_id)
    result = adapter.transition(approve, actor=REVIEWER)
    assert adapter.transition(approve, actor=REVIEWER) == result
    with pytest.raises(DomainError, match="changed payload"):
        adapter.transition(approve.model_copy(update={"reason": "different"}), actor=REVIEWER)
    monkeypatch.setattr("app.improvement.catalog.implementation_digest", lambda: "changed-source")
    with pytest.raises(DomainError, match="no longer matches"):
        adapter.transition(
            request("activate", patch_id=patch_id, probe_id=probe.probe_id), actor=REVIEWER
        )


def test_catalog_api_keeps_worker_and_reviewer_authority_separate(setup):
    service, clock, _ = setup
    with TestClient(
        create_app(
            service.repository.path,
            artifact_root=service.store.root,
            clock=clock,
            internal_token="synthetic-worker",
            reviewer_token="synthetic-reviewer",
            run_worker=False,
        )
    ) as client:
        command = request("approve", patch_id="unknown", probe_id="unknown").model_dump(mode="json")
        assert (
            client.post(
                "/api/catalog-improvements/review",
                json=command,
                headers={"X-Internal-Token": "synthetic-worker"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/catalog-improvements/commands",
                json=command,
                headers={"X-Internal-Token": "synthetic-worker"},
            ).status_code
            == 403
        )
        assert (
            client.get("/api/catalog-improvements/scopes/storage-2026").json()["active_version"]
            == BASE
        )
