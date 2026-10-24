from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.catalog.documents import compare
from app.catalog.requirements import specification
from app.contracts.catalog import ClarifyCommand, Policy, RequestCommand, RevisionCommand, Terms
from app.orders.service import DomainError

from .fixtures import accepted, draft_quote


def test_ambiguity_is_persisted_before_contract(setup):
    service, clock, _ = setup
    draft = service.create_request(
        RequestCommand(
            prompt="Find storage products under 2 kg and unit price no more than USD 40.",
            corpus_id="storage-2026",
            idempotency_key="draft",
        )
    )
    draft = service.compile_request(
        draft.request_id, RevisionCommand(expected_revision=1, idempotency_key="compile")
    )
    assert draft.status == "clarification" and draft.question.field == "weight_concept"
    deadline = draft.deadline
    clock.advance(5)
    answer = ClarifyCommand(
        expected_revision=draft.revision,
        idempotency_key="answer",
        question_id=draft.question.question_id,
        text="Net unit weight",
    )
    draft = service.clarify(draft.request_id, answer)
    assert draft.deadline == deadline
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile-again"),
    )
    assert draft.status == "ready"
    assert draft.specification.terms.weight_operator == "lt"
    assert draft.specification.terms.price_operator == "lte"
    assert {r.requirement_id for r in draft.specification.requirements} == {
        "R-CATEGORY",
        "R-WEIGHT",
        "R-PRICE",
        "R-FIELDS",
        "R-COMPLETENESS",
        "R-PROVENANCE",
        "R-PDF",
    }


@pytest.mark.parametrize(
    ("value", "operator", "limit", "expected"),
    [
        ("2", "lt", "2", False),
        ("2", "lte", "2", True),
        ("40", "lte", "40", True),
        ("40.01", "lte", "40", False),
    ],
)
def test_exact_thresholds(value, operator, limit, expected):
    assert compare(Decimal(value), operator, Decimal(limit)) == expected


def test_all_required_checks_are_server_owned(setup):
    service, _, _ = setup
    _, quote = draft_quote(service)
    terms = quote.specification.terms
    with pytest.raises(ValidationError):
        Terms.model_validate({**terms.model_dump(), "required_fields": ["product_id"]})
    assert (
        specification(terms, 9, "Changed wording", ()).requirements
        == quote.specification.requirements
    )
    with pytest.raises(ValidationError):
        Policy(review_seconds=600)


def test_clarification_timeout_and_budget(setup):
    service, clock, _ = setup
    draft = service.create_request(
        RequestCommand(prompt="Help me", corpus_id="storage-2026", idempotency_key="draft")
    )
    for index in range(3):
        draft = service.compile_request(
            draft.request_id,
            RevisionCommand(expected_revision=draft.revision, idempotency_key=f"c{index}"),
        )
        draft = service.clarify(
            draft.request_id,
            ClarifyCommand(
                expected_revision=draft.revision,
                idempotency_key=f"a{index}",
                question_id=draft.question.question_id,
                text="unsure",
            ),
        )
    draft = service.compile_request(
        draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="final")
    )
    assert draft.status == "human_review"
    clock.advance(301)
    assert service.get_request(draft.request_id).status == "human_review"


def test_quotes_are_server_owned_and_freeze_sources(setup):
    service, _, fixtures = setup
    order = accepted(service)
    frozen = order.snapshot.model_dump_json()
    original = fixtures["sources"][0]
    service.registry.register(original.model_copy(update={"version": 5}))
    assert service.get(order.snapshot.order_id).snapshot.model_dump_json() == frozen
    assert order.authorization.amount.amount_minor == 1500
    assert len(order.jobs) == 1 and order.authorization.receipt.status == "mock"
    assert order.authorization.receipt.transaction_id is None


def test_source_update_invalidates_unaccepted_quote(setup):
    from app.contracts.catalog import AcceptQuoteCommand

    service, _, fixtures = setup
    _, quote = draft_quote(service)
    service.registry.register(fixtures["sources"][0].model_copy(update={"version": 7}))
    with pytest.raises(DomainError, match="source registry changed"):
        service.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id, customer_actor="customer", idempotency_key="accept"
            )
        )


def test_expired_quote_and_client_extra_authority_rejected(setup):
    from app.contracts.catalog import AcceptQuoteCommand

    service, clock, _ = setup
    _, quote = draft_quote(service)
    clock.advance(180)
    with pytest.raises(DomainError, match="expired"):
        service.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id, customer_actor="customer", idempotency_key="accept"
            )
        )
    with pytest.raises(ValidationError):
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="customer", idempotency_key="accept", amount=1
        )
