"""Synthetic transport regressions; these are not counted as real Claude evidence."""

import json
from types import SimpleNamespace

import pytest

from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import Assessment, Provenance
from app.contracts.dataset import DatasetReference
from app.contracts.semantic import DatasetClaimReview, DatasetClauseReview
from app.investigation.dataset import semantic_attempt
from app.runtime.catalog_worker import CatalogWorker
from tests.dataset.test_lifecycle import dispute
from tests.dataset.test_semantic_primary import make_delivery

CLAIM = (
    "Our agreement excludes yoga-only participants, so treating their absence "
    "as a delivery defect would change the deal."
)


def wire(service, monkeypatch, *, invalid=None, slow=None):
    calls = []

    class Client:
        response_sink = None

        def __init__(self, **kwargs):
            self.messages = self

        def parse(self, **kwargs):
            packet = json.loads(kwargs["messages"][0]["content"])
            schema = kwargs["output_format"]
            calls.append((schema.__name__, packet))
            if schema is Assessment:
                refs = tuple(
                    DatasetReference.model_validate(p["citation"]) for p in packet["evidence"]
                )
                result = Assessment(
                    obligation_id=packet["requirement"]["obligation_id"],
                    result="PASS",
                    citations=refs,
                    reason_code="INJECTED_TEST_ONLY",
                    explanation="FIRST_ANSWER_MUST_NOT_REACH_REVIEWER",
                    provenance=Provenance(kind="model", assessor="test", version="1"),
                )
                if slow:
                    slow()
            else:
                if invalid == "timeout":
                    raise TimeoutError("Synthetic timeout")
                text = packet["complaint"]
                refs = tuple(
                    DatasetReference.model_validate(p["citation"])
                    for p in packet["frozen_evidence_packet"]["passages"]
                )
                if invalid == "omitted-clause" or invalid == "repair-success" and len(calls) == 2:
                    text = "Our agreement excludes yoga-only participants,"
                if invalid == "invented-ref":
                    refs = (refs[0].model_copy(update={"sha256": "0" * 64}),)
                if invalid == "no-citations":
                    refs = ()
                result = DatasetClaimReview(
                    result="UNKNOWN" if invalid == "disagree" else "PASS",
                    clauses=(
                        DatasetClauseReview(
                            text=text,
                            result="UNKNOWN" if invalid == "unknown-clause" else "PASS",
                            citations=refs,
                            explanation="Synthetic review fixture, not model evidence.",
                        ),
                    ),
                    explanation="Synthetic blind review fixture.",
                )
            if self.response_sink:
                self.response_sink(
                    {"synthetic_test": True, "parsed": result.model_dump(mode="json")}
                )
            return SimpleNamespace(stop_reason="end_turn", parsed_output=result)

        def close(self):
            pass

    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    monkeypatch.setattr("app.investigation.dataset.BoundedClient", Client)
    service.investigator = SimpleNamespace(
        assessor=ClaudeGateway(
            enabled=True,
            model="claude-opus-5-5",
            client=Client(),
        )
    )
    return calls


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "omitted-clause",
        "invented-ref",
        "no-citations",
        "disagree",
        "unknown-clause",
        "timeout",
    ],
)
def test_blind_review_requires_complete_grounded_agreement(dataset_service, monkeypatch, invalid):
    service, _ = dataset_service
    original = dispute(service, make_delivery(service), text=CLAIM)
    calls = wire(service, monkeypatch, invalid=invalid)
    assert CatalogWorker(service).run_once()
    current = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
    expected_calls = 3 if invalid in {"omitted-clause", "invented-ref", "no-citations"} else 2
    assert len(calls) == expected_calls and attempt.candidate.result == "PASS"
    assert "FIRST_ANSWER_MUST_NOT_REACH_REVIEWER" not in json.dumps(calls[1][1])
    assert attempt.effective.result == ("PASS" if invalid is None else "UNKNOWN")
    assert attempt.status == ("VALIDATED" if invalid is None else "ADVISORY")
    assert attempt.review_request["complaint"] == CLAIM
    assert attempt.raw_response and (attempt.review_response or attempt.review_failure)
    assert current.snapshot == original.snapshot and not current.ledger
    assert current.cases[-1].deadline == original.cases[-1].deadline
    assert not current.free_corrections_used


def test_one_completeness_repair_preserves_first_review_and_blindness(dataset_service, monkeypatch):
    service, _ = dataset_service
    original = dispute(service, make_delivery(service), text=CLAIM)
    calls = wire(service, monkeypatch, invalid="repair-success")
    assert CatalogWorker(service).run_once()
    current = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
    assert len(calls) == 3 and attempt.status == "VALIDATED"
    assert attempt.effective.result == "PASS" and not current.ledger
    assert attempt.review.clauses[0].text != CLAIM
    assert attempt.review_repair.clauses[0].text == CLAIM
    assert attempt.review_response and attempt.review_repair_response
    assert "FIRST_ANSWER_MUST_NOT_REACH_REVIEWER" not in json.dumps(calls[1:])
    assert "validation_error" in calls[2][1]["format_repair"]


def test_review_does_not_extend_existing_lease_or_deadline(dataset_service, monkeypatch):
    service, clock = dataset_service
    original = dispute(service, make_delivery(service), text=CLAIM)
    calls = wire(service, monkeypatch, slow=lambda: clock.advance(30))
    assert CatalogWorker(service).run_once()
    current = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, current)
    assert len(calls) == 1 and attempt.effective.result == "UNKNOWN"
    assert "Insufficient" in attempt.review_failure
    assert current.cases[-1].deadline == original.cases[-1].deadline and not current.ledger


def test_completed_review_survives_interruption_without_model_retry(dataset_service, monkeypatch):
    from app.orders.catalog import CatalogService
    from app.storage.catalog import CatalogRepository

    class Interrupted(BaseException):
        pass

    service, clock = dataset_service
    original = dispute(service, make_delivery(service), text=CLAIM)
    calls = wire(service, monkeypatch)

    def crash(*args, **kwargs):
        raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(service, "complete_verification", crash)
        with pytest.raises(Interrupted):
            service.run_one(original.snapshot.order_id)
    claimed = service.get(original.snapshot.order_id)
    with service.repository.transaction() as db:
        saved = semantic_attempt(db, claimed)
    assert saved.status == "VALIDATED" and len(calls) == 2
    clock.advance(45)
    restarted = CatalogService(
        CatalogRepository(service.repository.path),
        service.store.root,
        clock,
        assessor=service.investigator.assessor,
    )
    current = restarted.run_one(original.snapshot.order_id)
    assert len(calls) == 2 and current.semantic_findings[-1].result == "PASS"
    assert current.snapshot == original.snapshot and not current.ledger
