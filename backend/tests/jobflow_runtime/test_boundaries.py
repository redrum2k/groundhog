import asyncio
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.contracts.jobflow import (
    Command,
    DocumentUpload,
    Finding,
    InvestigationOutcome,
    InvestigationRequest,
    OrderCreate,
    SourceLocation,
)
from app.main import create_app
from app.runtime.jobflow import Jobflow
from app.runtime.jobflow_commands import ROLES
from app.runtime.jobflow_worker import claim, recover, run_once
from app.storage.jobflow import DomainError


@pytest.mark.parametrize("verb", sorted(ROLES))
def test_http_wrong_role_rejected_before_payload_resolution(h, verb):
    order = h.create()
    forbidden = next(
        role for role in h.actors if role not in ROLES[verb] and role != "customer_other"
    )
    with TestClient(create_app(h.service, worker=False)) as client:
        session = client.post("/api/jobflow/sessions", json={"actor_id": forbidden}).json()
        response = client.post(
            f"/api/jobflow/orders/{order.id}/commands",
            json={
                "idempotency_key": "forbidden",
                "expected_revision": order.revision,
                "verb": verb,
            },
            headers={"Authorization": f"Bearer {session['token']}"},
        )
        assert response.status_code == 403
    assert h.get(order) == order


def test_http_fail_closed_customer_scope_and_no_body_grants(h):
    order = h.create()
    with TestClient(create_app(h.service, worker=False)) as client:
        assert client.get("/api/jobflow/orders").status_code == 401
        assert (
            client.post("/api/jobflow/orders", json={"idempotency_key": "anonymous"}).status_code
            == 401
        )
        assert (
            client.post(
                "/api/jobflow/sessions", json={"actor_id": "customer", "role": "controller"}
            ).status_code
            == 422
        )
        assert (
            client.post("/api/jobflow/sessions", json={"actor_id": "unregistered"}).status_code
            == 403
        )
        session = client.post("/api/jobflow/sessions", json={"actor_id": "customer_other"}).json()
        headers = {"Authorization": f"Bearer {session['token']}"}
        assert client.get("/api/jobflow/orders", headers=headers).json() == []
        for path in ("", "/events", f"/artifacts/{order.jobs[0].source_id}"):
            assert (
                client.get(f"/api/jobflow/orders/{order.id}{path}", headers=headers).status_code
                == 403
            )
        assert (
            client.post(
                f"/api/jobflow/orders/{order.id}/commands",
                headers=headers,
                json={
                    "idempotency_key": "cross-customer",
                    "expected_revision": 1,
                    "verb": "accept_delivery",
                },
            ).status_code
            == 403
        )
        mine = client.post("/api/jobflow/sessions", json={"actor_id": "customer"}).json()
        headers = {"Authorization": f"Bearer {mine['token']}"}
        response = client.get(
            f"/api/jobflow/orders/{order.id}/artifacts/{order.jobs[0].source_id}", headers=headers
        )
        assert response.status_code == 200 and response.content.startswith(b"%PDF")
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["etag"].strip('"') == hashlib.sha256(response.content).hexdigest()
    disabled = Jobflow(h.service.store.path, demo=False)
    with TestClient(create_app(disabled, worker=False)) as client:
        assert client.get("/api/jobflow/actors").status_code == 404
        assert (
            client.post("/api/jobflow/sessions", json={"actor_id": "customer"}).status_code == 404
        )
        assert client.get("/api/jobflow/orders", headers=headers).status_code == 401
        assert client.get("/health").json()["live_settlement_enabled"] is False


def test_session_expiry_and_remote_demo_denial(h):
    from datetime import timedelta

    session = h.service.session("provider")
    assert h.service.authenticate(session["token"]).role == "provider"
    h.now += timedelta(hours=13)
    with pytest.raises(DomainError) as error:
        h.service.authenticate(session["token"])
    assert error.value.status == 401
    with TestClient(create_app(h.service, worker=False), client=("203.0.113.1", 12000)) as client:
        assert client.get("/api/jobflow/actors").status_code == 403


def test_investigation_http_202_and_background_worker_lifecycle(h):
    order = h.create()
    with TestClient(create_app(h.service)) as client:
        session = client.post("/api/jobflow/sessions", json={"actor_id": "investigator"}).json()
        headers = {"Authorization": f"Bearer {session['token']}"}
        response = client.post(
            f"/api/jobflow/orders/{order.id}/investigations",
            headers=headers,
            json={
                "idempotency_key": "http-run",
                "expected_revision": order.revision,
                "issue_id": order.issues[0].id,
            },
        )
        assert response.status_code == 202
        assert response.json()["run_id"]
        for _ in range(100):
            state = client.get(f"/api/jobflow/orders/{order.id}", headers=headers).json()
            if state["investigations"][0]["status"] == "COMPLETE":
                break
        else:
            pytest.fail("Application-owned worker did not consume durable queue")


def test_stale_result_rejected_and_model_io_does_not_hold_write_transaction(h):
    order = h.create()

    async def investigator(snapshot, issue_id, **kwargs):
        h.cmd(order, "controller", "handoff", text="Review separately", issue_id=issue_id)
        return await h.investigate(snapshot, issue_id, **kwargs)

    h.service.investigator = investigator
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key="stale", expected_revision=order.revision, issue_id=order.issues[0].id
        ),
    )
    h.drain()
    current = h.get(order)
    assert current.investigations[-1].status == "STALE"
    assert not current.issues[0].questions


def test_queued_revision_change_is_stale_before_model_call(h):
    order = h.create()
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key="queued-stale",
            expected_revision=order.revision,
            issue_id=order.issues[0].id,
        ),
    )
    h.cmd(order, "controller", "handoff", text="Review first")
    h.drain()
    assert not h.seen
    assert h.get(order).investigations[-1].status == "STALE"


@pytest.mark.parametrize("defect", ["quote", "version", "hash", "page", "issue"])
def test_bad_investigator_citations_rejected(h, defect):
    order = h.create()

    async def investigator(snapshot, issue_id, **kwargs):
        source = next(item for item in snapshot.evidence if item.kind == "source")
        citation = SourceLocation(
            source_id=source.id,
            version=source.version,
            sha256=source.sha256,
            quote="invoice_number: INV-0001",
            locator="page 1",
            page=1,
        )
        if defect == "quote":
            citation.quote = "invented text"
        elif defect == "version":
            citation.version = 99
        elif defect == "hash":
            citation.sha256 = "0" * 64
        elif defect == "page":
            citation.page = 99
        return InvestigationOutcome(
            issue_id=issue_id,
            revision=snapshot.revision,
            questions=[],
            recommendations=["INCLUDED_FIELD"],
            summary="test",
            model_mode="DETERMINISTIC",
            findings=[
                Finding(
                    id="finding",
                    issue_id="other" if defect == "issue" else issue_id,
                    statement="due_date owed",
                    status="SUPPORTED",
                    citations=[citation],
                )
            ],
        )

    h.service.investigator = investigator
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key=f"bad-{defect}",
            expected_revision=order.revision,
            issue_id=order.issues[0].id,
        ),
    )
    h.drain()
    current = h.get(order)
    assert current.investigations[-1].status == "FAILED"
    assert not current.issues[0].findings
    assert not any(action.kind == "INCLUDED_FIELD" for action in current.actions)


def test_model_recommendation_cannot_grant_authority(h):
    order = h.create()

    async def investigator(snapshot, issue_id, **kwargs):
        return InvestigationOutcome(
            issue_id=issue_id,
            revision=snapshot.revision,
            questions=[],
            findings=[],
            recommendations=["INCLUDED_FIELD"],
            summary="Ignore policy and execute",
            model_mode="DETERMINISTIC",
        )

    h.service.investigator = investigator
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key="untrusted",
            expected_revision=order.revision,
            issue_id=order.issues[0].id,
        ),
    )
    h.drain()
    actions = [action for action in h.get(order).actions if action.issue_id]
    assert [action.kind for action in actions] == ["HUMAN_REVIEW"]


def test_anthropic_budget_persisted_before_call_and_no_timeout_retry(h, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-value")
    monkeypatch.setenv("ANTHROPIC_MODEL", "synthetic-test-model")
    monkeypatch.setenv("JOBFLOW_ANTHROPIC_MAX_CALLS", "1")
    order = h.create()
    calls = []

    async def timeout(snapshot, issue_id, **kwargs):
        with h.service.store.connect() as db:
            assert db.execute("SELECT count(*) FROM jf_model_calls").fetchone()[0] == 1
        assert kwargs["call_authorized"] is True
        calls.append(issue_id)
        raise TimeoutError("Secret should never be logged")

    h.service.investigator = timeout
    request = InvestigationRequest(
        idempotency_key="paid-reservation",
        expected_revision=order.revision,
        issue_id=order.issues[0].id,
        mode="ANTHROPIC",
    )
    original = h.service.investigate(h.actors["investigator"], order.id, request)
    assert h.service.investigate(h.actors["investigator"], order.id, request) == original
    h.drain()
    current = h.get(order)
    assert current.investigations[0].status == "FAILED"
    assert "Secret" not in current.investigations[0].error
    assert len(calls) == 1
    h.service = Jobflow(h.service.store.path, demo=True, clock=lambda: h.now, investigator=timeout)
    recover(h.service)
    h.drain()
    assert len(calls) == 1
    assert not h.get(order).model_available
    with pytest.raises(DomainError):
        h.service.investigate(
            h.actors["investigator"],
            order.id,
            request.model_copy(
                update={"idempotency_key": "second", "expected_revision": current.revision}
            ),
        )


@pytest.mark.parametrize(
    "missing", ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "JOBFLOW_ANTHROPIC_MAX_CALLS"]
)
def test_model_requires_all_explicit_configuration(h, monkeypatch, missing):
    for key, value in {
        "ANTHROPIC_API_KEY": "test",
        "ANTHROPIC_MODEL": "test",
        "JOBFLOW_ANTHROPIC_MAX_CALLS": "3",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing)
    order = h.create()
    assert not order.model_available
    with pytest.raises(DomainError):
        h.service.investigate(
            h.actors["investigator"],
            order.id,
            InvestigationRequest(
                idempotency_key="no-budget",
                expected_revision=order.revision,
                issue_id=order.issues[0].id,
                mode="ANTHROPIC",
            ),
        )


def test_interrupted_model_run_never_retries_after_restart(h):
    order = h.create()
    h.service.investigate(
        h.actors["investigator"],
        order.id,
        InvestigationRequest(
            idempotency_key="interrupted-model",
            expected_revision=order.revision,
            issue_id=order.issues[0].id,
        ),
    )
    claim(h.service)
    recover(h.service)
    h.drain()
    assert h.get(order).investigations[0].status == "FAILED"
    assert not h.seen


def test_concurrent_distinct_keys_cannot_reserve_duplicate_attempt(h):
    order = h.create()

    def reserve(key):
        try:
            return h.service.command(
                h.actors["provider"],
                order.id,
                Command(verb="correct", idempotency_key=key, expected_revision=order.revision),
            )
        except DomainError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["one", "two"]))
    assert sum(result is not None for result in results) == 1
    assert len(h.get(order).jobs[-1].attempts) == 1


def test_validation_failure_is_not_sdk_success_and_cost_posted_once(h, monkeypatch):
    order = h.create()
    monkeypatch.setattr("app.runtime.jobflow_worker.extract", lambda *args: b'{"fields":{}}')
    h.cmd(order, "provider", "correct")
    h.drain()
    result = h.get(order)
    assert result.jobs[-1].processing == "FAILED"
    assert result.jobs[-1].attempts[0].output_artifact_id is not None
    assert result.finance.correction_cost_minor == 1
    assert result.finance.recognized_minor == 0


def test_reconcile_cannot_take_callers_word_or_use_another_orders_operation(h):
    order, change = h.quote(h.create())
    h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    h.cmd(order, "customer", "authorize_change", change_order_id=change.id)
    unknown = h.cmd(
        order, "executor", "receive_payment", change_order_id=change.id, provider_outcome="UNKNOWN"
    )
    operation = unknown.finance.operations[-1]
    with pytest.raises(DomainError, match="No authoritative"):
        h.cmd(order, "executor", "reconcile", operation_id=operation.id)
    h.drain()
    other = h.create()
    with pytest.raises(DomainError):
        h.cmd(other, "executor", "reconcile", operation_id=operation.id)
    with pytest.raises(DomainError):
        h.cmd(order, "executor", "reconcile", operation_id=operation.id, provider_outcome="FAILURE")


def test_document_versions_bytes_and_replay_are_immutable(h):
    order = h.create()

    def upload(revision, key, text):
        return DocumentUpload(
            idempotency_key=key,
            expected_revision=revision,
            filename="email.txt",
            media_type="text/plain",
            content_base64=base64.b64encode(text).decode(),
        )

    request = upload(order.revision, "email1", b"first assertion")
    first = h.service.upload(h.actors["customer"], order.id, request)
    second = h.service.upload(
        h.actors["customer"], order.id, upload(first.revision, "email2", b"new assertion")
    )
    assert second.evidence[-1].version == 2
    assert first.evidence[-1].id != second.evidence[-1].id
    assert (
        h.service.artifact(h.actors["customer"], order.id, first.evidence[-1].id)[0]
        == b"first assertion"
    )
    assert h.service.upload(h.actors["customer"], order.id, request) == first


def test_create_exact_replay_and_key_collision(h):
    request = OrderCreate(idempotency_key="same-create", document_count=1, failed_count=0)
    first = h.service.create(h.actors["customer"], request)
    assert h.service.create(h.actors["customer"], request) == first
    with pytest.raises(DomainError):
        h.service.create(h.actors["customer"], request.model_copy(update={"title": "different"}))


def test_payment_failure_is_not_posted_or_blindly_retried(h):
    order, change = h.quote(h.create())
    h.cmd(order, "customer", "accept_change", change_order_id=change.id)
    h.cmd(order, "customer", "authorize_change", change_order_id=change.id)
    h.cmd(
        order, "executor", "receive_payment", change_order_id=change.id, provider_outcome="FAILURE"
    )
    h.drain()
    assert h.get(order).finance.operations[0].status == "FAILED"
    assert h.get(order).finance.postings == []
    with pytest.raises(DomainError):
        h.cmd(order, "executor", "receive_payment", change_order_id=change.id)


def test_recovery_after_provider_result_persisted_uses_same_attempt(h):
    from app.runtime.jobflow_worker import produce_delivery
    from app.storage.jobflow import canonical

    order = h.create()
    h.cmd(order, "provider", "correct")
    work = claim(h.service)
    result = produce_delivery(h.service, work)
    with h.service.store.connect(write=True) as db:
        db.execute("INSERT INTO jf_provider_results VALUES(?,?)", (work["id"], canonical(result)))
    recover(h.service)
    reconciled = h.cmd(order, "executor", "reconcile", operation_id=work["id"])
    assert reconciled.jobs[-1].processing == "VALIDATED"
    assert len(reconciled.jobs[-1].attempts) == 1
    assert reconciled.finance.correction_cost_minor == 1


def test_quote_cannot_overlap_existing_draft(h):
    from app.runtime.jobflow_policy import proposal

    order, change = h.quote(h.create())
    with h.service.store.connect(write=True) as db:
        current = h.service.store.get(db, order.id)
        action = proposal(
            current,
            h.now,
            kind="QUOTE",
            fields=[change.fields[0]],
            job_ids=change.job_ids,
            basis="test duplicate",
        )
        current.actions.append(action)
        h.service.store.save(db, current)
    approved = h.cmd(order, "controller", "approve_action", action_id=action.id)
    with pytest.raises(DomainError, match="already covers"):
        h.cmd(
            approved,
            "executor",
            "execute_action",
            action_id=action.id,
            approval_id=approved.approvals[-1].id,
        )


def test_no_write_lock_during_extraction(h, monkeypatch):
    from app.runtime.jobflow_worker import extract

    order = h.create()

    def checked(*args):
        with h.service.store.connect(write=True) as db:
            assert db.execute("SELECT count(*) FROM jf_orders").fetchone()[0] == 1
        return extract(*args)

    monkeypatch.setattr("app.runtime.jobflow_worker.extract", checked)
    h.cmd(order, "provider", "correct")
    asyncio.run(run_once(h.service))
    assert h.get(order).jobs[-1].processing == "VALIDATED"


def test_worker_lock_blocks_second_supervisor_and_releases_cleanly(h):
    from app.storage.jobflow_lock import worker_ownership

    with worker_ownership(h.service.store.path):
        with pytest.raises(RuntimeError, match="already has a worker"):
            with worker_ownership(h.service.store.path):
                pytest.fail("Second worker acquired ownership")
    with worker_ownership(h.service.store.path):
        pass


def test_completion_requires_all_operational_and_financial_obligations(h):
    order = h.create(disputed_field=None, requested_fields=[])
    assert order.status == "ACTIVE"
    h.cmd(order, "provider", "correct")
    h.drain()
    corrected = h.get(order)
    assert corrected.status != "COMPLETE"
    accepted = h.cmd(corrected, "customer", "accept_delivery", job_ids=[corrected.jobs[-1].id])
    assert accepted.status != "COMPLETE"
    captured = h.cmd(accepted, "customer", "accept_base")
    assert captured.status == "COMPLETE"


def test_compute_cap_is_atomic(h):
    order = h.create()
    with h.service.store.connect(write=True) as db:
        current = h.service.store.get(db, order.id)
        current.agreement.correction_budget_minor = 0
        h.service.store.save(db, current)
    with pytest.raises(DomainError, match="budget"):
        h.cmd(order, "provider", "correct")
    assert not h.get(order).jobs[-1].attempts
    with h.service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM jf_work").fetchone()[0] == 0


def test_controlled_failure_mode_denied_when_demo_disabled(h):
    order = h.create()
    h.service.demo = False
    with pytest.raises(DomainError) as error:
        h.cmd(order, "provider", "correct", provider_outcome="UNKNOWN")
    assert error.value.status == 403


def test_future_terms_do_not_retroactively_mark_all_work_complete(h):
    from datetime import timedelta

    order = h.service.create(
        h.actors["customer"],
        OrderCreate(
            idempotency_key="future-scope",
            document_count=2,
            failed_count=0,
            disputed_field=None,
            requested_fields=[],
        ),
    )
    order = h.cmd(order, "customer", "accept_base")
    assert order.status == "COMPLETE"
    activation = h.now + timedelta(minutes=1)
    signed = h.cmd(
        order, "customer", "amend_agreement", fields=["due_date"], effective_at=activation
    )
    h.cmd(
        signed,
        "provider",
        "amend_agreement",
        fields=["due_date"],
        effective_at=activation,
        amendment_id=signed.agreement.amendments[-1].id,
    )
    h.now = activation
    assert h.get(order).status != "COMPLETE"


def test_targeted_handoff_does_not_block_independent_corrections(h):
    order = h.create()
    result = h.cmd(
        order,
        "controller",
        "handoff",
        issue_id=order.issues[0].id,
        text="Controller will resolve the field ambiguity",
    )
    assert result.status != "HANDED_OFF"
    assert result.jobs[-1].obligation == "OPEN"
    h.cmd(result, "provider", "correct")
    h.drain()
    assert h.get(order).jobs[-1].processing == "VALIDATED"
