from app.contracts.runs import RunDecision
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.payments.base_rpc import BaseTransportError
from tests.dataset.conftest import accepted
from tests.payments.test_catalog_settlement import Journey


def test_funding_audit_cannot_erase_a_later_failed_return(dataset_service, monkeypatch):
    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    service = journey.service
    order = accepted(service, payer=journey.buyer.address)
    order, _ = journey.authorize(order)
    service.payments.work()
    order = journey.confirm(order, "fund")
    with service.repository.transaction() as db:
        service._human(order, "Unresolved evidence requires review")
        order.revision += 1
        service._save(db, order)
    Runs(service).decide(
        order.snapshot.quote.request_id,
        RunDecision(binding=binding(order), action="approve", reason="Return uncaptured funds"),
        "return",
        "reviewer:test",
    )

    def failed(*args, **kwargs):
        raise BaseTransportError("eth_getCode unavailable; inspect/reconcile before retrying")

    monkeypatch.setattr(journey.chain, "prepare_transaction", failed)
    service.payments.work()
    assert journey.view(order).payment.payment.state == "failed"
    error = journey.view(order).payment.payment.last_error
    service.payments.executor.run_one(journey.operation(order, "fund").operation_id)
    assert journey.view(order).payment.payment.state == "failed"
    assert journey.view(order).payment.payment.last_error == error
    assert journey.operation(order, "void").transaction_hash is None
    assert not journey.current(order).ledger
