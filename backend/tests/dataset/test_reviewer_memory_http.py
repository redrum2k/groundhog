"""Actual HTTP lifecycle with injected model transport, including the blind review.

No browser/network listener is required; this is not a real-model quality result.
"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.agents.gateway import ClaudeGateway
from app.investigation import dataset
from app.main import create_app
from app.orders.runs import Runs
from tests.dataset.reviewer_memory_server import InjectedClient
from tests.dataset.test_reviewer_memory import AMBIGUOUS, FOLLOWUP, GUIDANCE, events, memories


def test_two_requests_through_http_keep_payment_gates_and_saved_receipts(
    dataset_service, monkeypatch
):
    original, clock = dataset_service
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    monkeypatch.setattr(dataset, "BoundedClient", InjectedClient)
    app = create_app(
        original.repository.path,
        artifact_root=original.store.root,
        clock=clock,
        run_worker=False,
        payment_mode="mock",
        internal_token="test-worker",
        reviewer_token="test-reviewer",
    )
    with TestClient(app) as client:
        service = app.state.orders
        service.investigator = SimpleNamespace(
            assessor=ClaudeGateway(
                enabled=True,
                model="injected-offline",
                client=InjectedClient(),
            )
        )

        def post(path, body, *, key="command", reviewer=False, worker=False):
            headers = {"Idempotency-Key": key}
            if reviewer:
                headers["X-Reviewer-Token"] = "test-reviewer"
            if worker:
                headers["X-Internal-Token"] = "test-worker"
            response = client.post(path, json=body, headers=headers)
            assert response.is_success, response.text
            return response.json()

        def current_page(run):
            after = 0
            while True:
                page = Runs(service).page(run, after=after)
                if page.caught_up:
                    return page
                after = page.next_after

        def bound(run):
            b = Runs(service).page(run).binding
            return {
                "expected_revision": b.revision,
                "expected_binding": {
                    "snapshot_id": b.snapshotId,
                    "delivery_version": b.deliveryVersion,
                    "evidence_revision": b.evidenceVersion,
                },
            }

        def deliver(key):
            run = post(
                "/runs",
                {
                    "prompt": (
                        "SF adults 25-34, gym membership or fitness app users, "
                        "by ZIP. Exclude yoga."
                    )
                },
                key=key,
            )["id"]
            draft = client.get(f"/requests/{run}").json()
            draft = post(
                f"/internal/requests/{run}/compile",
                {"expected_revision": draft["revision"], "idempotency_key": key + ":compile"},
                worker=True,
            )
            quote = post(
                f"/requests/{run}/quotes",
                {"expected_revision": draft["revision"], "idempotency_key": key + ":quote"},
            )
            view = post(
                "/quote-acceptance",
                {
                    "quote_id": quote["quote_id"],
                    "customer_actor": "AcmeFitness",
                    "idempotency_key": key + ":accept",
                },
            )
            order = view["order"]["snapshot"]["order_id"]
            prep = post(
                f"/orders/{order}/funding-preparation",
                {**bound(run), "idempotency_key": key + ":prepare"},
            )
            post(
                f"/orders/{order}/funding-authorizations",
                {
                    **bound(run),
                    "idempotency_key": key + ":fund",
                    "funding_attempt_id": prep["funding_attempt_id"],
                    "payment_hash": prep["terms"]["payment_hash"],
                    "simulate": True,
                },
            )
            service.payments.work()
            service.run_one(order)
            assert service.get(order).verification.passed
            return run, order

        run, order = deliver("first")
        post(
            f"/orders/{order}/complaints",
            {
                **bound(run),
                "idempotency_key": "easy",
                "text": "Regenerate the delivery because ZIP 94110 is missing.",
            },
        )
        service.run_one(order)
        assert service.get(order).cases[-1].status == "unsupported"
        first_deadline = service.get(order).deliveries[-1].review_deadline
        post(
            f"/orders/{order}/complaints",
            {**bound(run), "idempotency_key": "ambiguous", "text": AMBIGUOUS},
        )
        service.run_one(order)
        page = current_page(run)
        assert page.evidence_request and not memories(service)
        post(
            f"/runs/{run}/answers",
            {
                "binding": page.binding.model_dump(),
                "request_id": page.evidence_request.request_id,
                "text": "I cannot provide this evidence.",
            },
            key="no-evidence",
        )
        page = current_page(run)
        citation = next(
            e.evidence.id
            for e in events(service, run)
            if e.type == "evidence_found"
            and e.evidence.source.kind == "cell"
            and e.evidence.source.column == "yoga_is_gym"
        )
        decision = {
            "binding": page.binding.model_dump(),
            "action": "escalate",
            "reason": "Inspect the exact taxonomy cell, not only its label.",
            "guidance": GUIDANCE,
            "evidence_ids": [citation],
        }
        assert (
            client.post(
                f"/runs/{run}/decisions", json=decision, headers={"Idempotency-Key": "teach"}
            ).status_code
            == 403
        )
        saved = post(f"/runs/{run}/decisions", decision, key="teach", reviewer=True)
        assert post(f"/runs/{run}/decisions", decision, key="teach", reviewer=True) == saved
        assert len(memories(service)) == 1 and saved["guidance_memory_id"]
        assert service.get(order).deliveries[-1].review_deadline == first_deadline
        assert not service.get(order).ledger
        second, second_order = deliver("second")
        post(
            f"/orders/{second_order}/complaints",
            {**bound(second), "idempotency_key": "followup", "text": FOLLOWUP},
        )
        service.run_one(second_order)
        finding = [e.verdict.finding for e in events(service, second) if e.type == "verdict"][-1]
        assert finding.validation == "VALIDATED" and finding.effective.result == "FAIL"
        assert finding.reviewer_guidance[0].memory_id == saved["guidance_memory_id"]
        for ref in finding.reviewer_guidance[0].current_citations:
            service.store.resolve(ref, service.get(second_order).artifacts)
        assert not service.get(second_order).ledger
        post(
            f"/orders/{second_order}/acceptance",
            {**bound(second), "idempotency_key": "customer-accepts"},
        )
        service.payments.work()
        assert len(service.get(second_order).ledger) == 1
        assert not service.get(order).ledger
