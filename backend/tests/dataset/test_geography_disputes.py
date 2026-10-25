"""Frozen geographic scope, including the reported Oakland complaint, offline only."""

import json
from types import SimpleNamespace

import pytest

from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import AcceptQuoteCommand, Assessment, Provenance, QuoteRequest
from app.contracts.dataset import DatasetReference
from app.contracts.runs import RunOffer
from app.investigation.dataset import semantic_attempt
from app.orders.run_events import binding
from app.orders.runs import Runs
from tests.dataset.conftest import command, delivered, fund
from tests.dataset.test_complaint_text import body
from tests.dataset.test_intake_conversation import answer, start
from tests.dataset.test_review_boundary import client_for
from tests.dataset.test_review_payments import full_page


def exact_delivery(service):
    draft = answer(service, start(service), "Gym membership or fitness-app use")
    assert draft.status == "ready"
    quote = service.issue_quote(
        draft.request_id,
        QuoteRequest(expected_revision=draft.revision, idempotency_key="quote"),
    )
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id, customer_actor="AcmeFitness", idempotency_key="accept"
        )
    )
    return service.run_one(fund(service, order).snapshot.order_id)


def investigate(service, order, text):
    with client_for(service) as client:
        response = client.post(
            f"/orders/{order.snapshot.order_id}/complaints", json=body(order, text)
        )
        assert response.status_code == 200, response.text
    return service.run_one(order.snapshot.order_id)


def inject_geography_candidate(service, monkeypatch, result="FAIL", columns=True):
    """Exercise the actual ClaudeGateway/BoundedClient branch without network use."""
    calls = []

    class Client:
        response_sink = None

        def __init__(self, **kwargs):
            self.messages = self

        def parse(self, **kwargs):
            assert kwargs["output_format"] is Assessment  # No blind review is needed.
            packet = json.loads(kwargs["messages"][0]["content"])
            calls.append(packet)
            refs = tuple(
                DatasetReference.model_validate(p["citation"])
                for p in packet["evidence"]
                if p["citation"]["column"] == ("geography" if columns else "definition")
            )
            assessment = Assessment(
                obligation_id=packet["requirement"]["obligation_id"],
                result=result,
                citations=refs,
                reason_code="GEOGRAPHY_OUTSIDE_ACCEPTED_SCOPE",
                explanation=(
                    "The accepted San Francisco geography matches the frozen coverage registry "
                    "and source. Oakland is outside that scope; adding it requires a separate "
                    "accepted offer, not regeneration of this conforming delivery."
                ),
                provenance=Provenance(kind="model", assessor="injected-test", version="1"),
            )
            if self.response_sink:
                self.response_sink({"synthetic_test": True, "parsed": assessment.model_dump()})
            return SimpleNamespace(stop_reason="end_turn", parsed_output=assessment)

        def close(self):
            pass

    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    monkeypatch.setattr("app.investigation.dataset.BoundedClient", Client)
    service.investigator.assessor = ClaudeGateway(
        enabled=True, model="claude-opus-5-5", client=Client()
    )
    return calls


@pytest.mark.parametrize("model", [False, True])
@pytest.mark.parametrize("text", ["Oakland should be there", "Oakland should be in there."])
def test_reported_claim_resolves_from_frozen_scope_without_regeneration(
    dataset_service, monkeypatch, model, text
):
    service, _ = dataset_service
    original = exact_delivery(service)
    calls = inject_geography_candidate(service, monkeypatch) if model else []
    current = investigate(service, original, text)
    case, finding = current.cases[-1], current.semantic_findings[-1]
    assert finding.result == "FAIL" and case.status == "unsupported"
    assert not case.question and case.questions_asked == 0
    assert current.snapshot == original.snapshot and current.sources == original.sources
    assert current.deliveries == original.deliveries and current.free_corrections_used == 0
    assert not current.children and not current.ledger
    assert current.authorization.expires_at == original.authorization.expires_at
    assert "San Francisco" in finding.explanation and "Oakland" in finding.explanation
    assert "separate accepted offer" in finding.explanation
    assert {r.source_id for r in finding.citations} == {
        "sf-aggregate-v1:coverage",
        "sf-aggregate-v1:gym_or_fitness_app",
    }
    for ref in finding.citations:
        assert ref.column == "geography" and service.store.resolve(ref, current.artifacts)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
    assert attempt.status == "VALIDATED" and attempt.effective.result == "FAIL"
    assert len(calls) == int(model)
    if model:
        assert attempt.raw_response["synthetic_test"]
        assert attempt.candidate.reason_code == "GEOGRAPHY_OUTSIDE_ACCEPTED_SCOPE"
        assert finding.provenance.kind == "model" and attempt.review is None
    page = full_page(service, current.snapshot.quote.request_id)
    verdict = next(e.verdict for e in page.events if e.type == "verdict")
    assert verdict.kind == "disagree" and verdict.reason == finding.explanation
    assert all(not a.enabled for a in page.available_actions if a.action in {"approve", "ask"})
    # A finding alone never captures. Explicit delivery acceptance uses existing gates.
    accepted = service.mutate(current.snapshot.order_id, "accept", command(current, "delivery"))
    service.payments.work()
    paid = service.get(accepted.snapshot.order_id)
    assert len(paid.ledger) == 1 and paid.ledger[0].kind == "capture"
    assert paid.deliveries == original.deliveries


@pytest.mark.parametrize(
    "text,result",
    [
        ("Oakland should also be included in the dataset.", "FAIL"),
        ("Oakland is included in our agreed geography.", "FAIL"),
        ("The accepted geographic scope covers Oakland.", "FAIL"),
        ("San Francisco should be there.", "PASS"),
        ("SF should be included in the delivered CSV.", "PASS"),
        ("Oakland should not be included.", "PASS"),
        ("Oakland should be there, and these counts are duplicated.", "UNKNOWN"),
        ("Oakland residents are present in these counts.", "UNKNOWN"),
        ("Oakland is in the dataset.", "UNKNOWN"),
        ("Oakland should be included because our separate agreement promised it.", "UNKNOWN"),
        ("Berkeley should be there.", "UNKNOWN"),
        ("Oakland should be there for free.", "UNKNOWN"),
    ],
)
def test_scope_predicate_preserves_negation_qualifiers_and_empirical_claims(
    dataset_service, text, result
):
    service, _ = dataset_service
    original = delivered(service)
    current = investigate(service, original, text)
    assert current.semantic_findings[-1].result == result
    assert (current.cases[-1].status == "unsupported") == (result == "FAIL")
    assert current.deliveries == original.deliveries and not current.ledger
    assert not current.free_corrections_used


@pytest.mark.parametrize(
    "text,result", [("Oakland should be in there.", "PASS"), ("SF should be there.", "FAIL")]
)
def test_geographic_truth_changes_with_the_accepted_product(dataset_service, text, result):
    service, _ = dataset_service
    parent = delivered(service)
    quote = Runs(service).offer(
        parent.snapshot.quote.request_id,
        RunOffer(binding=binding(parent), scope="oakland"),
        "oakland-offer",
        "provider:test",
    )
    child = service.accept_quote(
        AcceptQuoteCommand(quote_id=quote.quote_id, customer_actor="buyer", idempotency_key="child")
    )
    child = service.run_one(fund(service, child).snapshot.order_id)
    current = investigate(service, child, text)
    assert current.semantic_findings[-1].result == result
    assert (current.cases[-1].status == "unsupported") == (result == "FAIL")
    assert not current.ledger and not current.free_corrections_used
    assert current.snapshot == child.snapshot and current.deliveries == child.deliveries


@pytest.mark.parametrize("result,columns", [("PASS", True), ("FAIL", False)])
def test_model_disagreement_or_unrelated_citations_cannot_dismiss_complaint(
    dataset_service, monkeypatch, result, columns
):
    service, _ = dataset_service
    original = delivered(service)
    calls = inject_geography_candidate(service, monkeypatch, result=result, columns=columns)
    current = investigate(service, original, "Oakland should be there.")
    assert len(calls) == 1
    assert current.semantic_findings[-1].result == "UNKNOWN"
    assert current.cases[-1].status == "open" and current.cases[-1].question
    assert current.deliveries == original.deliveries and not current.ledger


def test_unavailable_frozen_geography_cannot_establish_unsupported_claim(dataset_service):
    service, _ = dataset_service
    original = delivered(service)
    coverage = next(s for s in original.sources if s.source_id.endswith(":coverage"))
    path = service.store.root / coverage.artifact.storage_key
    path.write_bytes(b"{}")
    current = investigate(service, original, "Oakland should be there.")
    assert current.cases[-1].status != "unsupported"
    assert not current.ledger and not current.free_corrections_used
