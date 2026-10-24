import pytest

from app.contracts.broker import BrokerCommand, DraftCreate
from app.storage.jobflow import DomainError, uid
from tests.broker.conftest import ACTORS, accept_order, command, parameters, source_bytes


def test_C02_C03_pass_opens_review_and_accepts_once(broker):
    order = accept_order(broker)
    assert not order.base_order.order.ledger
    order = command(broker, order, "provider", "produce")
    assert order.base_order.order.data_verification.verdict == "PASS"
    assert order.colour == "green"
    assert not order.base_order.order.ledger
    request = BrokerCommand(
        idempotency_key=uid("accept"), expected_revision=order.revision, verb="accept_delivery"
    )
    accepted = broker.command(ACTORS["customer"], order.id, request)
    replay = broker.command(ACTORS["customer"], order.id, request)
    assert accepted == replay
    assert len(accepted.base_order.order.ledger) == 1
    assert accepted.base_order.order.ledger[0].amount.amount_minor == 1000


def test_C04_verified_cutoff_and_C07_separate_authorization(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    broker.clock.advance(599)
    assert not broker.view(ACTORS["customer"], order.id).base_order.order.ledger
    broker.clock.advance(1)
    assert len(broker.view(ACTORS["customer"], order.id).base_order.order.ledger) == 1
    other = command(broker, accept_order(broker, auth_seconds=10), "provider", "produce")
    broker.clock.advance(10)
    held = broker.view(ACTORS["customer"], other.id)
    assert held.base_order.order.payment_phase == "expired"
    assert not held.base_order.order.ledger
    assert held.human_tasks[0].owner == "controller"


def test_S03_stale_observation_fresh_export_fails_then_bounded_handoff(broker):
    raw = source_bytes(
        rows=[
            dict(
                entity_id="region-001",
                region_id="R001",
                value=95000.0,
                observed_at="2024-01-01T00:00:00Z",
            )
        ]
    )
    order = command(broker, accept_order(broker, raw=raw), "provider", "produce")
    assert order.base_order.order.data_verification.verdict == "FAIL"
    assert order.base_order.order.regeneration_pending
    assert not order.base_order.order.ledger
    order = command(broker, order, "provider", "produce")
    assert order.base_order.order.free_regenerations_used == 1
    assert order.base_order.order.order_state == "human_review"
    assert order.human_tasks[0].owner == "controller"


def test_S04_C05_missing_date_unknown_cutoff_holds(broker):
    raw = source_bytes(
        rows=[dict(entity_id="region-001", region_id="R001", value=95000.0, observed_at=None)]
    )
    order = command(broker, accept_order(broker, raw=raw), "provider", "produce")
    assert order.base_order.order.data_verification.verdict == "UNKNOWN"
    assert order.questions[0].recipient == "provider"
    broker.clock.advance(600)
    held = broker.view(ACTORS["customer"], order.id)
    assert held.base_order.order.payment_phase == "held"
    assert not held.base_order.order.ledger
    assert held.human_tasks[0].state == "OPEN"


def test_C11_refuted_complaint_no_remedy_no_fee(broker):
    order = command(broker, accept_order(broker), "provider", "produce")
    order = command(broker, order, "customer", "dispute", text="The observation is too old.")
    order = command(broker, order, "investigator", "investigate")
    assert order.resolution == "NO_REMEDY"
    assert not order.base_order.order.ledger
    assert not order.base_order.order.requires_quote
    order = command(broker, order, "customer", "accept_delivery")
    assert len(order.base_order.order.ledger) == 1


def test_intake_never_invents_recent_or_authorizes_unaccepted_draft(broker):
    draft = broker.create_draft(
        ACTORS["customer"], DraftCreate(idempotency_key=uid("draft"), intent="recent data")
    )
    assert draft.parameters.max_age_days is None
    assert "max_age_days" in draft.unresolved_fields
    with broker.store.connect() as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 0
        assert (
            db.execute("SELECT count(*) FROM im_records WHERE kind='incident'").fetchone()[0] == 1
        )


def test_S05_tenant_and_role_boundaries(broker):
    order = accept_order(broker)
    with pytest.raises(DomainError, match="another customer"):
        broker.view(ACTORS["customer_other"], order.id)
    with pytest.raises(DomainError, match="Role"):
        command(broker, order, "customer", "produce")


def test_csv_actual_artifact_and_pdf_are_verified(broker):
    order = command(
        broker, accept_order(broker, params=parameters(output_format="csv")), "provider", "produce"
    )
    assert order.base_order.order.data_verification.verdict == "PASS"
    content = [
        broker.artifact(ACTORS["customer"], order.id, identifier)
        for identifier in order.delivery_artifact_ids
    ]
    assert any(
        meta["filename"] == "market-data.csv" and b"entity_id" in raw for raw, meta, _ in content
    )
    assert any(raw.startswith(b"%PDF-") for raw, _, _ in content)
