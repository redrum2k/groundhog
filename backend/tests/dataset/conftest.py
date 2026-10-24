import pytest

from app.contracts.catalog import AcceptQuoteCommand, OrderCommand, QuoteRequest, RevisionCommand
from app.contracts.payments import FundingAuthorization
from app.contracts.runs import RunCreate
from app.orders.catalog import CatalogService
from app.orders.runs import Runs
from app.runtime.catalog_worker import CatalogWorker
from app.storage.catalog import CatalogRepository
from tests.catalog.fixtures import Clock


@pytest.fixture
def dataset_service(tmp_path):
    clock = Clock()
    service = CatalogService(
        CatalogRepository(tmp_path / "orders.sqlite3"), tmp_path / "artifacts", clock
    )
    return service, clock


def command(order, key):
    return OrderCommand(
        expected_revision=order.revision, expected_binding=order.binding, idempotency_key=key
    )


def accepted(service, key="request", payer=None):
    run = Runs(service).create(
        RunCreate(prompt="SF adults 25–34, gym members or fitness app users, by ZIP."), key
    )
    draft = service.get_request(run.id)
    draft = service.compile_request(
        run.id, RevisionCommand(expected_revision=draft.revision, idempotency_key="compile:" + key)
    )
    quote = service.issue_quote(
        run.id,
        QuoteRequest(expected_revision=draft.revision, idempotency_key="quote:" + key, payer=payer),
    )
    return service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="AcmeFitness", idempotency_key="accept:" + key
        )
    )


def fund(service, order):
    prep = service.payments.prepare(order.snapshot.order_id, command(order, "prepare"))
    service.payments.authorize(
        order.snapshot.order_id,
        FundingAuthorization(
            **command(order, "fund").model_dump(),
            funding_attempt_id=prep.funding_attempt_id,
            payment_hash=prep.terms.payment_hash,
            simulate=True,
        ),
    )
    service.payments.work()
    return service.get(order.snapshot.order_id)


def delivered(service):
    order = fund(service, accepted(service))
    assert CatalogWorker(service).run_once()
    return service.get(order.snapshot.order_id)
