"""An exhausted evidence source needs a human, not another paid investigation."""

import pytest

from app.contracts.runs import RunEvidenceAnswer
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.storage.catalog import CatalogRepository
from tests.dataset.test_review_answers import question


@pytest.mark.parametrize(
    "text",
    [
        "I have no additional source documentation or evidence "
        "to resolve this authenticity concern.",
        "I don't have any more evidence.",
        "I cannot provide this evidence.",
        "I can't provide evidence.",
    ],
)
def test_unavailable_evidence_hands_off_atomically_without_another_job(dataset_service, text):
    service, clock = dataset_service
    order, assessor, _ = question(service)
    run = order.snapshot.quote.request_id
    api = Runs(service)
    command = RunEvidenceAnswer(
        binding=binding(order),
        request_id=api.page(run).evidence_request.request_id,
        text=text,
    )
    calls = len(assessor.inputs)
    ack = api.answer(run, command, "unavailable")
    assert api.answer(run, command, "unavailable") == ack
    saved = service.get(order.snapshot.order_id)
    assert saved.order_state == "human_review"
    assert saved.cases[-1].status == "human_review"
    assert saved.cases[-1].questions_asked == 1
    assert saved.cases[-1].question is None
    assert saved.cases[-1].deadline == order.cases[-1].deadline
    assert len(saved.evidence_answers) == 1
    assert len(saved.jobs) == len(order.jobs)
    assert len(assessor.inputs) == calls
    assert not saved.ledger and not saved.semantic_findings
    page = api.page(run)
    while not page.caught_up:
        page = api.page(run, after=page.next_after)
    assert page.evidence_request is None
    assert page.payment.payment.state == "funded"
    assert next(a for a in page.available_actions if a.action == "approve").enabled
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    assert restarted.get(order.snapshot.order_id).order_state == "human_review"


@pytest.mark.parametrize(
    "text",
    [
        "If I have no additional evidence, what happens?",
        'The provider said "I have no additional evidence."',
        "I have no additional evidence, but the registered authority proves my claim.",
        "I have more evidence.",
    ],
)
def test_other_testimony_still_gets_investigated(dataset_service, text):
    service, _ = dataset_service
    order, _, _ = question(service)
    run = order.snapshot.quote.request_id
    api = Runs(service)
    api.answer(
        run,
        RunEvidenceAnswer(
            binding=binding(order),
            request_id=api.page(run).evidence_request.request_id,
            text=text,
        ),
        "answer",
    )
    saved = service.get(order.snapshot.order_id)
    assert saved.order_state == "processing"
    assert saved.jobs[-1].kind == "reverify" and saved.jobs[-1].status == "queued"
