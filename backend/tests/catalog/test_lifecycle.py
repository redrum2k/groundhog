from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contracts.catalog import AcceptQuoteCommand, CatalogOrder, OfferCommand, ReviewCommand
from app.orders.catalog import CatalogService
from app.orders.service import DomainError
from app.storage.catalog import CatalogRepository

from .fixtures import accepted, cmd, draft_quote, repaired, upload


def test_repair_journey_requires_review_then_books_once(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    assert order.order_state == "delivered" and order.verification.passed
    assert order.ledger == ()
    assert order.amendments[-1].classification == "evidence_only"
    assert order.free_corrections_used == 0 and len(order.deliveries) == 1
    assert order.snapshot.quote.sources[1].version == 1 and order.sources[1].version == 2
    assert order.snapshot.quote.sources[1].artifact in order.artifacts
    clock.advance(59)
    assert service.expire_due() == 0
    clock.advance(1)
    assert service.expire_due() == 1
    assert service.expire_due() == 0
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    result = restarted.get(order.snapshot.order_id)
    assert result.order_state == "closed" and len(result.ledger) == 1
    assert result.ledger[0].receipt.status == "mock"
    assert result.ledger[0].receipt.transaction_id is None


def test_pre_delivery_repair_does_not_fabricate_delivery(setup):
    service, _, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    assert order.order_state == "waiting_evidence" and not order.deliveries
    assert order.binding.delivery_version == 0
    assert order.evidence_requests[0].target_source.source_id == "supplier-b"
    assert not order.ledger and order.free_corrections_used == 0
    assert any(a.reason_code == "REQUIRED_VALUE_UNREADABLE" for a in order.verification.assessments)


@pytest.mark.parametrize(
    ("fixture", "code", "result"),
    [
        ("unregistered", "SOURCE_AUTHORITY_UNVERIFIED", "UNKNOWN"),
        ("date_conflict", "EFFECTIVE_DATE_CONFLICT", "CONFLICT"),
    ],
)
def test_unresolved_amendment_escalates_with_actionable_table(setup, fixture, code, result):
    service, clock, fixtures = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    deadline = order.repair_deadline
    artifact = fixtures[fixture] if fixture == "unregistered" else fixtures[fixture].artifact
    order = upload(service, order, artifact)
    order = service.run_one(order.snapshot.order_id)
    assert order.amendments[-1].assessment[0].reason_code == code
    assert order.amendments[-1].assessment[0].result == result
    assert order.order_state == "waiting_evidence" and len(order.evidence_requests) == 2
    assert order.repair_deadline == deadline
    clock.advance(120)
    order = service.get(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.ledger
    rows = service.view(order).human_review
    relevant = next(r for r in rows if r.field == "amendment_authority")
    assert relevant.accepted_wording and relevant.source_citations and relevant.required_authority
    assert relevant.financial_effect and relevant.recommended_remedy and relevant.result == result


def test_two_unresolved_attempts_escalate_without_reset(setup):
    service, _, fixtures = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    for index in range(2):
        order = upload(service, order, fixtures["unregistered"], f"upload-{index}")
        order = service.run_one(order.snapshot.order_id)
    assert order.order_state == "human_review" and len(order.evidence_requests) == 2


def test_substantive_amendment_requires_new_accepted_work(setup):
    service, _, fixtures = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    snapshot = order.snapshot
    order = upload(service, order, fixtures["substantive"].artifact)
    order = service.run_one(order.snapshot.order_id)
    assert order.amendments[-1].classification == "substantive"
    assert order.authority_state == "pending_consent" and not order.ledger
    quote = service.offer(
        order.snapshot.order_id,
        cmd(
            order,
            "offer",
            OfferCommand,
            work_description="Use the proposed catalog facts and regenerate the shortlist.",
            terms=order.snapshot.quote.specification.terms,
            amendment_id=order.amendments[-1].amendment_id,
        ),
        actor="provider:trusted",
    )
    acceptance = AcceptQuoteCommand(
        quote_id=quote.quote_id, customer_actor="customer:test", idempotency_key="child"
    )
    child = service.accept_quote(acceptance)
    assert service.accept_quote(acceptance) == child
    assert (
        len(child.jobs) == 1
        and child.authorization.authorization_id != order.authorization.authorization_id
    )
    assert child.snapshot.quote.sources[1].version == fixtures["substantive"].version
    parent = service.get(order.snapshot.order_id)
    assert parent.snapshot == snapshot and parent.ledger[-1].kind == "release"
    assert service.run_one(child.snapshot.order_id).verification.passed


def test_paid_additional_offer_creates_one_separate_job(setup):
    service, _, fixtures = setup
    order = repaired(service, fixtures)
    quote = service.offer(
        order.snapshot.order_id,
        cmd(
            order,
            "offer",
            OfferCommand,
            work_description="Produce another shortlist using shipping weight.",
            terms=order.snapshot.quote.specification.terms.model_copy(
                update={"weight_concept": "shipping"}
            ),
        ),
        actor="provider:test",
    )
    assert not service.get(order.snapshot.order_id).ledger
    request = AcceptQuoteCommand(
        quote_id=quote.quote_id, customer_actor="customer:test", idempotency_key="paid"
    )
    with ThreadPoolExecutor(2) as executor:
        first, second = list(executor.map(service.accept_quote, [request, request]))
    assert first == second and len(first.jobs) == 1
    parent = service.get(order.snapshot.order_id)
    assert (
        parent.authorization.amount.amount_minor == 1500
        and first.authorization.amount.amount_minor == 500
    )
    assert len(parent.children) == 1


def test_acceptance_concurrency_and_changed_idempotency_payload(setup):
    service, clock, _ = setup
    _, quote = draft_quote(service)
    request = AcceptQuoteCommand(
        quote_id=quote.quote_id, customer_actor="customer:test", idempotency_key="accept"
    )
    with ThreadPoolExecutor(4) as executor:
        orders = list(executor.map(service.accept_quote, [request] * 4))
    assert all(order == orders[0] for order in orders)
    with pytest.raises(DomainError, match="changed request"):
        service.accept_quote(request.model_copy(update={"customer_actor": "different"}))
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    assert restarted.accept_quote(request) == orders[0]


def test_restart_recovers_expired_worker_lease_and_rejects_old_result(setup):
    service, clock, _ = setup
    order = accepted(service)
    reserved, old_job = service.claim_job(order.snapshot.order_id)
    clock.advance(45)
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    current, replacement = restarted.claim_job(order.snapshot.order_id)
    assert replacement.job_id == old_job.job_id and replacement.attempts == 2
    with pytest.raises(DomainError, match="stale"):
        service.fail_job(order.snapshot.order_id, old_job, "late worker failure")
    assert (
        restarted.fail_job(order.snapshot.order_id, replacement, "provider offline").order_state
        == "operational_failure"
    )


def test_missing_verification_never_becomes_timeout_capture(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    with service.repository.transaction() as db:
        order.verification = None
        service._save(db, order)
    clock.advance(60)
    order = service.get(order.snapshot.order_id)
    assert order.order_state == "human_review" and not order.ledger


def test_expired_authority_blocks_customer_and_reviewer_capture(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    clock.advance(3600)
    order = service.get(order.snapshot.order_id)
    assert order.authorization.status == "expired" and not order.ledger
    with pytest.raises(DomainError):
        service.mutate(order.snapshot.order_id, "accept", cmd(order, "accept"))
    with pytest.raises(ValueError):
        ReviewCommand(
            expected_revision=order.revision,
            expected_binding=order.binding,
            idempotency_key="override",
            action="capture",
            reason="override",
            supporting_evidence=(),
        )


def test_reviewer_records_exception_without_rewriting_facts_and_can_release(setup):
    service, clock, fixtures = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    clock.advance(120)
    order = service.get(order.snapshot.order_id)
    evidence = (order.verification.assessments[0].citations[0],)
    original = order.snapshot
    command = cmd(
        order,
        "exception",
        ReviewCommand,
        action="propose_exception",
        reason="Negotiation proposed; no finding changed.",
        supporting_evidence=evidence,
    )
    order = service.mutate(order.snapshot.order_id, "review", command, actor="reviewer:trusted")
    assert order.decisions[-1].negotiated_exception and order.snapshot == original
    assert not order.ledger and order.authority_state == "pending_consent"
    request = cmd(
        order,
        "release",
        ReviewCommand,
        action="release_authorization",
        reason="Unable to obtain agreed evidence.",
        supporting_evidence=evidence,
    )
    order = service.mutate(order.snapshot.order_id, "review", request, actor="reviewer:trusted")
    assert order.ledger[0].kind == "release" and order.authorization.status == "released"
    assert order.decisions[-1].actor == "reviewer:trusted"


def test_legacy_json_and_idempotent_responses_remain_unchanged(setup):
    service, clock, _ = setup
    raw = '{"policy":"historical-600-seconds","ledger":[{"fee":250}],"unknown_field":true}'
    with service.repository.transaction() as db:
        db.execute("INSERT INTO orders VALUES (?,?)", ("old", raw))
        db.execute(
            "INSERT INTO order_commands VALUES (?,?,?,?)", ("old", "key", "original request", raw)
        )
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    clock.advance(9999)
    restarted.expire_due()
    with restarted.repository.transaction() as db:
        assert db.execute("SELECT data FROM orders WHERE order_id='old'").fetchone()[0] == raw
        assert (
            db.execute("SELECT response FROM order_commands WHERE order_id='old'").fetchone()[0]
            == raw
        )
        assert not restarted.repository.all(db, "order", CatalogOrder)
