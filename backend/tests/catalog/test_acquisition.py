from app.catalog.acquisition import acquire_registered, registered_repair
from tests.catalog.fixtures import accepted


def test_competent_fixed_recipe_reaches_registered_repair_floor(setup):
    service, _, fixtures = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    original_snapshot = order.snapshot
    assert registered_repair(service, order) == fixtures["repair"]
    acquired = acquire_registered(service, order)
    assert acquired.amendments[-1].actor == "system:registered-evidence-acquisition"
    assert acquired.snapshot == original_snapshot
    order = service.run_one(acquired.snapshot.order_id)
    order = service.run_one(order.snapshot.order_id)
    assert order.verification.passed and order.order_state == "delivered"
    assert not order.ledger  # Acquisition is not customer acceptance/capture.
    assert order.free_corrections_used == 0


def test_recipe_does_not_use_changed_known_values_as_repair(setup):
    service, _, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    # Remove only the synthetic test's valid repair registration, not the source
    # bytes or accepted terms. The remaining changed-value/date candidates fail.
    with service.repository.transaction() as db:
        db.execute("DELETE FROM catalog_sources WHERE source_id='supplier-b' AND version=2")
    assert registered_repair(service, order) is None
    assert acquire_registered(service, order) == order
    assert not order.deliveries and not order.ledger


def test_recipe_rechecks_current_authority_and_deadline(setup):
    service, clock, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    clock.advance(121)
    assert registered_repair(service, order) is None
    assert acquire_registered(service, order) == order
