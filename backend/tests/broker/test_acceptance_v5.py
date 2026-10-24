"""V5 acceptance journeys against actual bytes and the existing mock ledger."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from app.contracts.broker import BrokerCommand, DraftCreate, SourceUpload
from app.contracts.models import Money, PaymentState
from app.data_products import build_package, current_data_verification, source_pin
from app.orders.service import DomainError as OrderError
from app.runtime.broker import Broker
from app.runtime.jobflow import Jobflow
from app.storage.jobflow import DomainError, canonical, uid
from tests.broker.conftest import (
    ACTORS,
    accept_order,
    command,
    enable_clarity,
    parameters,
    source_bytes,
)


def offered_draft(broker, *, parent=None, sources=None):
    """Stop at the consent boundary which accept_order intentionally crosses."""
    enable_clarity(broker)
    draft = broker.create_draft(
        ACTORS["customer"],
        DraftCreate(
            idempotency_key=uid("draft"),
            parent_order_id=parent,
            intent="Regional household income, separately priced and accepted.",
        ),
    )
    for raw in sources or [source_bytes()]:
        draft = broker.upload(
            ACTORS["provider"],
            draft.id,
            SourceUpload(
                idempotency_key=uid("source"),
                expected_revision=draft.revision,
                filename="regional-source.json",
                content_base64=base64.b64encode(raw).decode(),
            ),
        )
    values = parameters().model_dump(mode="json")
    for question in list(draft.questions):
        draft = broker.draft_command(
            ACTORS["customer"],
            draft.id,
            BrokerCommand(
                idempotency_key=uid("answer"),
                expected_revision=draft.revision,
                verb="answer_intake",
                question_id=question.id,
                value=values[question.field],
            ),
        )
    return broker.draft_command(
        ACTORS["provider"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("offer"),
            expected_revision=draft.revision,
            verb="offer",
            capability="SUPPORTED",
            price=Money(amount_minor=750, currency="USDSIM", decimals=2),
        ),
    )


def upload_revision(broker, order, raw):
    order = broker.view(ACTORS["provider"], order.id)
    return broker.upload(
        ACTORS["provider"],
        order.id,
        SourceUpload(
            idempotency_key=uid("source"),
            expected_revision=order.revision,
            filename="regional-source.json",
            content_base64=base64.b64encode(raw).decode(),
        ),
        accepted=True,
    )


def amend(broker, order, specification, effective_at):
    order = command(
        broker,
        order,
        "customer",
        "propose_amendment",
        specification=specification,
        effective_at=effective_at,
    )
    amendment = order.amendments[-1]
    for role in ("customer", "provider"):
        order = command(
            broker,
            order,
            role,
            "accept_amendment",
            amendment_id=amendment.id,
            digest=amendment.digest,
        )
    return order


def missing_date():
    return source_bytes(
        rows=[dict(entity_id="region-001", region_id="R001", value=95000, observed_at=None)]
    )


def bad_data_package(specification, sources):
    """A faulty provider supplies actual wrong output, not a runtime mutation flag."""
    package = build_package(specification, sources)
    name, media, raw = package[0]
    data = json.loads(raw)
    data["rows"][0]["value"] = 1
    package[0] = (name, media, canonical(data).encode())
    return package


def test_C06_concurrent_capture_and_dispute_have_serializable_outcome(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    barrier = Barrier(2)
    requests = {
        verb: BrokerCommand(
            idempotency_key=uid(verb),
            expected_revision=order.revision,
            verb=verb,
            text="The delivered income is incorrect." if verb == "dispute" else None,
        )
        for verb in ("accept_delivery", "dispute")
    }

    def submit(verb):
        barrier.wait(timeout=10)
        try:
            return broker.command(ACTORS["customer"], order.id, requests[verb])
        except (DomainError, OrderError) as exc:
            assert exc.status == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, requests))
    assert sum(result is not None for result in results) == 1
    current = broker.view(ACTORS["customer"], order.id)
    if results[1] is None:
        # The losing customer refreshes and can still raise a post-capture remedy case.
        current = command(broker, current, "customer", "dispute", text=requests["dispute"].text)
        assert len(current.base_order.order.ledger) == 1
        assert current.base_order.order.payment_phase == "booked"
    else:
        assert not current.base_order.order.ledger
        assert current.base_order.order.payment_phase == "held"
    assert current.base_order.order.case_state == "open"
    assert current.base_order.order.complaint == requests["dispute"].text
    with pytest.raises(OrderError):
        command(broker, current, "customer", "accept_delivery")
    broker.clock.advance(600)
    final = broker.view(ACTORS["customer"], order.id)
    assert final.base_order.order.order_state == "human_review"
    assert len(final.base_order.order.ledger) == (results[0] is not None)


@pytest.mark.parametrize("trigger", ["accept", "cutoff"])
def test_C08_time_only_amendment_activation_invalidates_cached_pass(broker, trigger):
    order = command(broker, accept_order(broker), "provider", "produce")
    snapshot = order.base_order.order.snapshot
    # No source changes: activation alone must invalidate the prior verification.
    specification = order.original_specification.model_copy(update={"version": 2})
    order = amend(broker, order, specification, broker.clock() + timedelta(seconds=600))
    assert order.base_order.order.data_verification is None
    order = command(broker, order, "investigator", "investigate")
    assert current_data_verification(order.base_order.order, broker.clock())
    broker.clock.advance(599)
    assert current_data_verification(order.base_order.order, broker.clock())
    broker.clock.advance(1)
    assert not current_data_verification(order.base_order.order, broker.clock())
    held = broker.view(ACTORS["customer"], order.id)
    if trigger == "accept":
        with pytest.raises(OrderError):
            command(broker, held, "customer", "accept_delivery")
    assert held.base_order.order.order_state == "human_review"
    assert not held.base_order.order.ledger
    assert held.base_order.order.snapshot == snapshot
    assert held.original_specification == snapshot.data_specification


def test_C08_unilateral_amendment_never_changes_accepted_terms(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    snapshot = order.base_order.order.snapshot
    order = command(
        broker,
        order,
        "customer",
        "propose_amendment",
        specification=order.original_specification.model_copy(update={"version": 2}),
        effective_at=broker.clock(),
    )
    proposed = order.amendments[-1]
    order = command(
        broker,
        order,
        "customer",
        "accept_amendment",
        amendment_id=proposed.id,
        digest=proposed.digest,
    )
    assert not order.base_order.order.data_amendments
    assert current_data_verification(order.base_order.order, broker.clock())
    assert order.base_order.order.snapshot == snapshot
    with pytest.raises(DomainError, match="exact proposed terms"):
        command(
            broker,
            order,
            "provider",
            "accept_amendment",
            amendment_id=proposed.id,
            digest="0" * 64,
        )


def test_C08_new_source_invalidates_action_and_preserves_accepted_source(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    snapshot = order.base_order.order.snapshot
    stale = BrokerCommand(
        idempotency_key=uid("accept"), expected_revision=order.revision, verb="accept_delivery"
    )
    order = upload_revision(broker, order, source_bytes(version=2, metric_name="individual_income"))
    assert order.base_order.order.data_verification is None
    assert order.base_order.order.snapshot == snapshot
    with pytest.raises(DomainError, match="stale"):
        broker.command(ACTORS["customer"], order.id, stale)
    with pytest.raises(OrderError, match="current spec/evidence"):
        command(broker, order, "customer", "accept_delivery")
    order = command(broker, order, "investigator", "investigate")
    # Merely uploading v2 cannot silently replace the mutually accepted v1 source.
    assert order.base_order.order.data_verification.verdict == "PASS"
    source_citations = [
        citation
        for check in order.base_order.order.data_verification.checks
        for citation in check.citations
        if citation.source_id == "regional-census"
    ]
    assert source_citations
    assert {c.version for c in source_citations} == {1}


def test_C09_wrong_delivered_value_gets_one_free_changed_revalidated_package(broker):
    broker.producer = bad_data_package
    order = command(broker, accept_order(broker), "provider", "produce")
    original_snapshot = order.base_order.order.snapshot
    first_id = order.delivery_artifact_ids[0]
    bad_raw, bad_meta, _ = broker.artifact(ACTORS["customer"], order.id, first_id)
    assert json.loads(bad_raw)["rows"][0]["value"] == 1
    assert order.base_order.order.data_verification.verdict == "FAIL"
    assert order.base_order.order.regeneration_pending
    assert not order.base_order.order.ledger
    with pytest.raises(OrderError):
        command(broker, order, "customer", "accept_delivery")
    broker.producer = build_package
    broker.clock.advance(10)
    order = command(broker, order, "provider", "produce")
    good_raw, good_meta, _ = broker.artifact(
        ACTORS["customer"], order.id, order.delivery_artifact_ids[0]
    )
    assert json.loads(good_raw)["rows"][0]["value"] == 95000
    assert bad_raw != good_raw and bad_meta["sha256"] != good_meta["sha256"]
    assert broker.artifact(ACTORS["customer"], order.id, first_id)[0] == bad_raw
    assert order.base_order.order.binding.delivery_version == 2
    assert order.base_order.order.free_regenerations_used == 1
    assert current_data_verification(order.base_order.order, broker.clock())
    assert order.base_order.order.review_deadline == broker.clock() + timedelta(seconds=600)
    assert order.base_order.order.snapshot == original_snapshot
    assert not order.base_order.order.ledger
    order = command(broker, order, "customer", "accept_delivery")
    assert [(entry.kind, entry.amount.amount_minor) for entry in order.base_order.order.ledger] == [
        ("base", 1000)
    ]


@pytest.mark.parametrize("failure", ["semantic", "operational"])
def test_C10_failed_free_correction_escalates_without_further_attempts(broker, failure):
    broker.producer = bad_data_package
    order = command(broker, accept_order(broker), "provider", "produce")
    if failure == "operational":

        def unavailable(specification, sources):
            raise ValueError("Provider transport unavailable")

        broker.producer = unavailable
    order = command(broker, order, "provider", "produce")
    assert order.base_order.order.order_state == "human_review"
    assert order.base_order.order.free_regenerations_used == 1
    assert not order.base_order.order.ledger
    assert order.human_tasks[0].state == "OPEN"
    versions = len(order.base_order.order.deliveries)
    with pytest.raises(DomainError, match="Production requires"):
        command(broker, order, "provider", "produce")
    current = broker.view(ACTORS["customer"], order.id)
    assert len(current.base_order.order.deliveries) == versions
    assert not current.base_order.order.ledger


def test_C10_initial_operational_failures_stop_at_overall_case_deadline(broker):
    calls = []

    def unavailable(specification, sources):
        calls.append(specification.version)
        raise ValueError("Provider transport unavailable")

    broker.producer = unavailable
    order = accept_order(broker)
    for _ in range(3):
        order = command(broker, order, "provider", "produce")
        assert not order.base_order.order.deliveries
        assert not order.base_order.order.ledger
    broker.clock.advance(1800)
    current = broker.view(ACTORS["customer"], order.id)
    try:
        command(broker, current, "provider", "produce")
    except DomainError as exc:
        assert exc.status == 409
    assert len(calls) == 3, "The provider was invoked again after the overall case deadline"
    assert current.base_order.order.order_state == "human_review", (
        "Repeated initial failures remain retryable at the overall case deadline"
    )
    with pytest.raises(DomainError):
        command(broker, current, "provider", "produce")
    assert len(calls) == 3


def test_C12_added_scope_has_independent_draft_quote_consent_and_decline(broker):
    parent = command(broker, accept_order(broker), "provider", "produce")
    original = parent.base_order.order.model_dump(mode="json")
    draft = offered_draft(broker, parent=parent.id)
    assert draft.order_id is None and draft.offered_price.amount_minor == 750
    assert draft.provider_accepted_digest and draft.customer_accepted_digest is None
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
    declined = broker.draft_command(
        ACTORS["customer"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("decline"), expected_revision=draft.revision, verb="decline"
        ),
    )
    assert declined.status == "DECLINED"
    assert (
        broker.view(ACTORS["customer"], parent.id).base_order.order.model_dump(mode="json")
        == original
    )
    offered = offered_draft(broker, parent=parent.id)
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
    accepted = broker.draft_command(
        ACTORS["customer"],
        offered.id,
        BrokerCommand(
            idempotency_key=uid("accept"),
            expected_revision=offered.revision,
            verb="accept_specification",
            digest=offered.acceptance_digest,
            authorization_expires_at=broker.clock() + timedelta(hours=1),
        ),
    )
    child = broker.view(ACTORS["customer"], accepted.order_id)
    assert child.parent_order_id == parent.id
    assert child.base_order.order.authorization_id != parent.base_order.order.authorization_id
    draft = broker.draft(ACTORS["customer"], child.id)
    assert draft.offered_price == Money(amount_minor=750, currency="USDSIM", decimals=2)
    assert (
        draft.customer_accepted_digest == draft.provider_accepted_digest == draft.acceptance_digest
    )
    assert not child.base_order.order.ledger
    assert (
        broker.view(ACTORS["customer"], parent.id).base_order.order.model_dump(mode="json")
        == original
    )
    parent = command(broker, parent, "customer", "accept_delivery")
    assert len(parent.base_order.order.ledger) == 1
    assert not broker.view(ACTORS["customer"], child.id).base_order.order.ledger


def test_C14_exact_answer_replay_resumes_once_without_deadline_or_delivery_change(broker):
    order = command(broker, accept_order(broker, raw=missing_date()), "provider", "produce")
    question = order.questions[-1]
    deadline = order.base_order.order.review_deadline
    deliveries = order.base_order.order.deliveries
    broker.clock.advance(100)
    request = BrokerCommand(
        idempotency_key=uid("answer"),
        expected_revision=order.revision,
        verb="answer",
        question_id=question.id,
        text="I believe the observation is recent; no dated record is available.",
    )
    answered = broker.command(ACTORS["provider"], order.id, request)
    replay = broker.command(ACTORS["provider"], order.id, request)
    assert replay == answered
    restarted = Broker(Jobflow(broker.store.path, demo=True, clock=broker.clock))
    assert restarted.command(ACTORS["provider"], order.id, request) == answered
    with pytest.raises(DomainError) as changed_replay:
        restarted.command(
            ACTORS["provider"],
            order.id,
            request.model_copy(
                update={"text": "A different assertion under the same idempotency key"}
            ),
        )
    assert changed_replay.value.status == 409
    assert answered.base_order.order.review_deadline == deadline
    assert answered.base_order.order.deliveries == deliveries
    assert answered.base_order.order.data_verification.verdict == "UNKNOWN"
    assert (
        answered.base_order.order.binding.evidence_version == question.binding.evidence_version + 1
    )
    assert answered.question_count == 2
    assert not answered.base_order.order.ledger
    events = broker.events(ACTORS["customer"], order.id)
    resumed = [event for event in events if event["type"] == "case.resumed"]
    assert len(resumed) == 1
    assert resumed[0]["payload"]["issue_id"] == question.issue_id
    with pytest.raises(DomainError, match="closed or stale"):
        command(broker, answered, "provider", "answer", question_id=question.id, text=request.text)
    broker.clock.advance(500)
    held = broker.view(ACTORS["customer"], order.id)
    assert held.base_order.order.order_state == "human_review"
    assert not held.base_order.order.ledger


def test_C15_human_task_resumes_only_after_current_source_facts_are_revalidated(broker):
    order = command(broker, accept_order(broker, raw=missing_date()), "provider", "produce")
    for _ in range(2):
        question = next(q for q in order.questions if q.status == "OPEN")
        order = command(
            broker,
            order,
            "provider",
            "answer",
            question_id=question.id,
            text="The source has no authenticated observation date yet.",
        )
    task = order.human_tasks[0]
    assert task.state == "OPEN" and task.owner == "controller"
    assert task.missing_facts and task.evidence and task.next_action
    order = command(
        broker,
        order,
        "controller",
        "resolve_human",
        task_id=task.id,
        decision="RESUME",
        text="Please check whether current source facts resolve the gap.",
    )
    assert order.human_tasks[0].state == "OPEN"
    assert order.base_order.order.order_state == "human_review"
    assert not order.base_order.order.ledger
    raw = source_bytes(version=2)
    order = upload_revision(broker, order, raw)
    specification = order.original_specification.model_copy(
        update={"version": 2, "sources": (source_pin(raw),)}
    )
    order = amend(broker, order, specification, broker.clock())
    order = command(
        broker,
        order,
        "controller",
        "resolve_human",
        task_id=task.id,
        decision="RESUME",
        text="Both parties accepted the authenticated dated source revision.",
    )
    assert order.human_tasks[0].state == "RESOLVED"
    assert order.base_order.order.regeneration_pending
    assert not order.base_order.order.ledger
    order = command(broker, order, "provider", "produce")
    assert current_data_verification(order.base_order.order, broker.clock())
    assert order.base_order.order.binding.delivery_version == 2
    assert order.base_order.order.snapshot.data_specification.version == 1
    assert order.base_order.order.data_amendments[-1].specification == specification


@pytest.mark.parametrize("state", [PaymentState.UNCERTAIN, PaymentState.SUBMITTED])
def test_C16_uncertain_base_payment_survives_restart_and_cannot_capture(broker, state):
    order = command(broker, accept_order(broker), "provider", "produce")
    with broker.store.connect(write=True) as db:
        base = broker.base.repository.get(db, order.id)
        base.payment_state = state
        base.revision += 1
        broker.base.repository.save(db, base)
    restarted = Broker(Jobflow(broker.store.path, demo=True, clock=broker.clock))
    with pytest.raises(OrderError, match="active, undisputed"):
        command(restarted, order, "customer", "accept_delivery")
    current = restarted.view(ACTORS["customer"], order.id)
    assert current.base_order.order.payment_state == state
    assert current.base_order.order.authorization_id == order.base_order.order.authorization_id
    assert not current.base_order.order.ledger
    assert current.base_order.order.order_state == "human_review"
    assert current.base_order.order.payment_phase == "held"
    assert "reconciliation" in current.base_order.order.failure
    assert current.human_tasks[0].owner == "controller"
