import pytest

from app.runtime.catalog_policy import capture_allowed
from tests.catalog.fixtures import accepted, cmd, repaired


def test_passing_verification_alone_never_bypasses_review(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    assert not capture_allowed(order, clock())
    order.customer_acceptance = order.binding
    assert capture_allowed(order, clock())


@pytest.mark.parametrize("state", ["pending", "uncertain", "expired", "released"])
def test_unconfirmed_authorization_blocks_dispatch(setup, state):
    from app.orders.service import DomainError

    service, _, _ = setup
    order = accepted(service)
    order.authorization = order.authorization.model_copy(update={"status": state})
    with service.repository.transaction() as db:
        service._save(db, order)
    with pytest.raises(DomainError):
        service.claim_job(order.snapshot.order_id)


def test_removed_mandatory_check_cannot_authorize_capture(setup):
    service, clock, fixtures = setup
    order = repaired(service, fixtures)
    report = order.verification
    order.verification = report.model_copy(
        update={
            "obligations": tuple(o for o in report.obligations if o.obligation_id != "global:pdf"),
            "assessments": tuple(a for a in report.assessments if a.obligation_id != "global:pdf"),
        }
    )
    clock.advance(60)
    assert not capture_allowed(order, clock())


def test_accept_and_dispute_concurrency_has_one_winner(setup):
    from concurrent.futures import ThreadPoolExecutor

    from app.contracts.catalog import Complaint, DisputeCommand
    from app.orders.service import DomainError

    service, _, fixtures = setup
    order = repaired(service, fixtures)
    dispute = cmd(
        order,
        "dispute",
        DisputeCommand,
        complaint=Complaint(
            text="Please check weight",
            product_id="S01",
            field="weight",
            requirement_id="R-WEIGHT",
            artifact_id=order.deliveries[-1].pdf.artifact_id,
        ),
    )

    def perform(item):
        operation, command = item
        try:
            service.mutate(order.snapshot.order_id, operation, command)
            return "ok"
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(perform, [("accept", cmd(order, "accept")), ("dispute", dispute)]))
    assert results.count("ok") == 1 and results.count(409) == 1
    current = service.get(order.snapshot.order_id)
    assert len(current.ledger) <= 1
    assert not (current.ledger and any(case.status == "open" for case in current.cases))
