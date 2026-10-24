"""Functional, adversarial and causal regressions for simulated institutional knowledge."""

import json
import os
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.aggregate.execution import offline_guards
from evals.source_learning.fixtures import (
    CUSTOMER,
    OWNER,
    engine,
    make_case,
    resolution_evidence,
    setup_source,
)
from tools.brokerage_acceptance import Clock, fund

from app.agents.source_knowledge import InstitutionalMemory, SourceKnowledge
from app.agents.source_preparation import compile_prepared_source
from app.contracts.catalog import AcceptQuoteCommand, QuoteRequest
from app.datasets import canonical, parse_csv
from app.orders.catalog import CatalogService
from app.orders.service import DomainError
from app.storage.catalog import CatalogRepository


@pytest.fixture
def service(tmp_path):
    system_root = os.environ.get("SystemRoot")
    with (
        offline_guards(),
        patch.dict(os.environ, {"SystemRoot": system_root} if system_root else {}),
    ):
        yield CatalogService(
            CatalogRepository(tmp_path / "orders.sqlite3"), tmp_path / "artifacts", Clock()
        )


def learn(service, inputs, column=None, book="candidate"):
    learner = engine(service, book)
    case = make_case(service, inputs, "first-" + book)
    first = learner.assess(case)
    assert first["status"] == "internal_review" and first["reason"] == "ambiguous_source_definition"
    proof = resolution_evidence(service, case, inputs[2], column or inputs[2].columns[0])
    resolution = learner.resolve(first["encounter_id"], proof, trusted_actor=OWNER)
    procedure = learner.induce(resolution["id"])
    return learner, case, first, resolution, procedure


def pointer(data, path):
    for component in path.strip("/").split("/"):
        data = data[int(component)] if isinstance(data, list) else data[component]
    return data


def test_complete_cycle_changes_later_order_and_keeps_customer_consent(service):
    inputs = setup_source(service)
    learner, first_case, first, resolution, procedure = learn(service, inputs)
    later = make_case(service, inputs, "different-later-order", ("94110", "94129"))
    baseline = engine(service, "empty-stateless").assess(later)
    assert baseline["internal_reviews"] == 1 and not baseline["rows"]
    # A new object uses only persisted experience, not a Python object/session cache.
    learner = engine(service, "candidate")
    reused = learner.assess(later)
    assert reused["internal_reviews"] == 0 and reused["procedure_id"] == procedure["id"]
    assert reused["resolution_id"] == resolution["id"]
    assert reused["rows"] == [
        {"zip": "94110", "count": 179, "status": "released"},
        {"zip": "94129", "count": None, "status": "suppressed"},
    ]
    assert reused["customer_consent_required"] and baseline["customer_consent_required"]
    assert first_case.request_id != later.request_id
    for citation in reused["citations"]:
        raw = json.loads((service.store.root / citation["artifact"]["storage_key"]).read_bytes())
        assert pointer(raw, citation["pointer"]) == citation["value"]
    draft = compile_prepared_source(
        learner, reused["encounter_id"], idempotency_key="prepare-later"
    )
    assert draft.status == "ready" and draft.order_id is None
    quote = service.issue_quote(
        later.request_id,
        QuoteRequest(
            expected_revision=draft.revision,
            idempotency_key="quote-later",
        ),
    )
    assert len(quote.sources) == 8
    assert not quote.specification.terms.provenance[0].reference_id == first_case.request_id
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id,
            customer_actor=CUSTOMER,
            idempotency_key="accept-later",
        )
    )
    assert not order.deliveries and order.authorization.status == "pending"
    order = fund(service, order)
    assert order.delivery_state == "verified" and order.verification.passed
    rows = parse_csv(service.store.read(order.deliveries[-1].csv))
    assert next(r.count for r in rows if r.zip == "94110") == 179
    assert not order.ledger
    assert learner.memory.records("source_procedure")[0]["column"] == inputs[2].columns[0]


def test_new_batch_reads_new_values_using_edition_scoped_experience(service):
    first = setup_source(service)
    learner, _, _, _, procedure = learn(service, first)
    later_inputs = setup_source(service, batch=2)
    later = make_case(service, later_inputs, "new-batch", ("94110",))
    assert later.source.artifact.sha256 != first[0].artifact.sha256
    result = engine(service, "candidate").assess(later)
    assert result["procedure_id"] == procedure["id"]
    assert result["rows"][0]["count"] == 192  # Fresh batch, not the prior 179.
    assert engine(service, "empty").assess(later)["internal_reviews"] == 1
    assert result["binding"]["source"]["sha256"] == later.source.artifact.sha256


def test_two_complete_real_brokerage_orders_with_private_resolution_history(service):
    from evals.source_learning.run import finish_order

    inputs = setup_source(service)
    learner, first_case, _, _, _ = learn(service, inputs)
    first_order = finish_order(learner, learner.assess(first_case), "first")
    inputs2 = setup_source(service, batch=2)
    case2 = make_case(service, inputs2, "later-full-order", ("94110",))
    assert engine(service, "stateless").assess(case2)["internal_reviews"] == 1
    ready = engine(service, "candidate").assess(case2)
    later_order = finish_order(engine(service, "candidate"), ready, "later")
    assert first_order["order_id"] != later_order["order_id"]
    assert first_order["snapshot"] == service.get(first_order["order_id"]).snapshot.model_dump(
        mode="json"
    )
    assert (
        len({first_order["delivery"]["csv"]["sha256"], later_order["delivery"]["csv"]["sha256"]})
        == 2
    )


def test_commercial_action_guard_rejects_actual_attempt(service):
    from evals.source_learning.run import forbid_commercial_actions

    attempts = []
    with (
        forbid_commercial_actions(service, attempts),
        pytest.raises(RuntimeError, match="commercial"),
    ):
        service.accept_quote(None)
    assert attempts == ["commercial_action_attempt"]


@pytest.mark.parametrize(
    "columns,chosen",
    [
        (("m17", "m42"), 0),
        (("m17", "m42"), 1),
        (("u81", "q09"), 1),
        (("observations", "adults"), 0),
    ],
)
def test_behavior_comes_from_resolution_not_column_names_or_cached_answer(service, columns, chosen):
    inputs = setup_source(service, columns=columns)
    learner, _, _, _, procedure = learn(service, inputs, columns[chosen])
    later = make_case(service, inputs, "new-case", ("94103",))
    result = learner.assess(later)
    assert result["column"] == columns[chosen]
    assert result["rows"][0]["count"] == (137 if chosen == 0 else 237)
    assert "rows" not in procedure and "final_answer" not in procedure
    assert not engine(service, "empty").assess(later)["rows"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"source_version": 2, "head_version": 2, "reverse": True}, "ambiguous_source_definition"),
        ({"head_version": 2, "epoch": "dictionary-2"}, "ambiguous_source_definition"),
        ({"head_version": 2, "status": "revoked"}, "authority_revoked"),
        ({"head_version": 2, "status": "conflict"}, "authority_conflict"),
        ({"head_version": 2, "expired": True}, "authority_expired"),
        (
            {
                "head_version": 2,
                "definitions": (("m17", "unique_adults_per_zip"), ("m42", "unique_adults_per_zip")),
            },
            "conflicting_current_definitions",
        ),
    ],
)
def test_changed_or_conflicting_authority_never_reuses_procedure(service, change, reason):
    inputs = setup_source(service)
    learner, _, _, _, _ = learn(service, inputs)
    changed = setup_source(service, **change)
    later = make_case(service, changed, "contrasting-order", ("94110",))
    result = learner.assess(later)
    assert result["reason"] == reason and result["internal_reviews"] == 1
    assert result["procedure_id"] is None and result["rows"] == []
    assert engine(service, "empty").assess(later)["reason"] == reason


def test_competent_baseline_uses_current_definition_without_memory(service):
    inputs = setup_source(service, definitions=(("m42", "unique_adults_per_zip"),))
    case = make_case(service, inputs, "already-documented", ("94110",))
    result = engine(service, "stateless").assess(case)
    assert result["internal_reviews"] == 0 and result["column"] == "m42"
    assert result["rows"][0]["count"] == 279 and result["procedure_id"] is None


def test_new_current_authority_overrides_old_mapping_without_memory_reuse(service):
    learner, _, _, _, _ = learn(service, setup_source(service))
    changed = setup_source(
        service,
        head_version=2,
        epoch="dictionary-2",
        definitions=(("m42", "unique_adults_per_zip"),),
    )
    case = make_case(service, changed, "new-authority", ("94110",))
    result = learner.assess(case)
    assert result["rows"][0]["count"] == 279 and result["procedure_id"] is None
    assert result["reason"] == "current_authoritative_definition"


@pytest.mark.parametrize("mutation", ["actor", "source", "authority", "scope", "unit", "column"])
def test_resolution_requires_trusted_source_bound_evidence(service, mutation):
    inputs = setup_source(service)
    learner = engine(service, "candidate")
    case = make_case(service, inputs, "pending")
    result = learner.assess(case)
    artifact = resolution_evidence(service, case, inputs[2], "m17")
    proof = json.loads(service.store.read(artifact))
    if mutation == "actor":
        proof["actor_id"] = "customer:untrusted"
    elif mutation == "source":
        proof["source_pin"]["version"] = 99
    elif mutation == "authority":
        proof["authority_pin"]["sha256"] = "0" * 64
    elif mutation == "scope":
        proof["scope"]["geography"] = "Oakland"
    elif mutation == "unit":
        proof["definition"]["unit"] = "households"
    elif mutation == "column":
        proof["definition"]["column"] = "nonexistent"
    bad = service.store.put(canonical(proof), "application/json")
    with pytest.raises(ValueError):
        learner.resolve(result["encounter_id"], bad, trusted_actor=OWNER)
    assert not learner.memory.records("source_procedure")


def test_order_only_resolution_cannot_be_promoted_to_institutional_rule(service):
    inputs = setup_source(service)
    learner = engine(service, "candidate")
    case = make_case(service, inputs, "pending")
    result = learner.assess(case)
    proof = resolution_evidence(service, case, inputs[2], "m17", applicability="this_order_only")
    resolution = learner.resolve(result["encounter_id"], proof, trusted_actor=OWNER)
    with pytest.raises(ValueError, match="order-specific"):
        learner.induce(resolution["id"])


def test_conflicting_retained_resolutions_fail_closed(service):
    inputs = setup_source(service)
    learner, case, first, _, _ = learn(service, inputs)
    conflicting = resolution_evidence(service, case, inputs[2], "m42")
    other = learner.resolve(first["encounter_id"], conflicting, trusted_actor=OWNER)
    learner.induce(other["id"])
    result = learner.assess(make_case(service, inputs, "later"))
    assert result["reason"] == "conflicting_retained_definition" and not result["rows"]


def test_durable_scope_and_immutability_and_no_production_activation(service):
    inputs = setup_source(service)
    learner, _, _, _, procedure = learn(service, inputs)
    with pytest.raises(ValueError, match="sandbox"):
        InstitutionalMemory(service.repository.path, CUSTOMER, "candidate")
    with pytest.raises(ValueError):
        engine(service, "candidate", customer="OtherBuyer").memory.get(
            "source_procedure", procedure["id"]
        )
    with learner.memory.store.connect(write=True) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM im_records WHERE id=?", (procedure["id"],))
        assert db.execute("SELECT count(*) FROM im_active").fetchone()[0] == 0


def test_revoked_resolver_grant_prevents_reuse(service):
    inputs = setup_source(service)
    learner, _, _, _, _ = learn(service, inputs)
    no_grant = SourceKnowledge(service, learner.memory, {}, sandbox=True)
    with pytest.raises(ValueError, match="lacks"):
        no_grant.assess(make_case(service, inputs, "later"))


def test_stale_head_and_customer_scope_cannot_be_hidden(service):
    inputs = setup_source(service)
    learner, _, _, _, _ = learn(service, inputs)
    case = make_case(service, inputs, "later")
    with pytest.raises(ValueError, match="customer"):
        engine(service, "candidate", customer="OtherBuyer").assess(case)
    setup_source(service, head_version=2, status="revoked")
    with pytest.raises(ValueError, match="no longer current"):
        learner.assess(case)


def test_no_published_source_before_resolution(service):
    inputs = setup_source(service)
    learner = engine(service, "empty")
    result = learner.assess(make_case(service, inputs, "pending"))
    with pytest.raises(ValueError, match="unresolved"):
        compile_prepared_source(learner, result["encounter_id"], idempotency_key="blocked")
    assert service.registry.manifest(inputs[0].corpus_id)[0]
    with learner.memory.store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM catalog_records WHERE kind='order'").fetchone()[0] == 0
        )


def test_completed_preparation_retry_returns_saved_response_without_side_effects(service):
    learner, case, _, _, _ = learn(service, setup_source(service))
    ready = learner.assess(case)
    draft = compile_prepared_source(learner, ready["encounter_id"], idempotency_key="retry")
    with patch.object(learner, "assess", side_effect=AssertionError("retry reassessed")):
        replay = compile_prepared_source(learner, ready["encounter_id"], idempotency_key="retry")
    assert replay == draft
    # Retry survives a new service/memory instance and even subsequent expiry.
    service.clock.now += timedelta(hours=3)
    restarted = CatalogService(service.repository, service.store.root, service.clock)
    assert (
        compile_prepared_source(
            engine(restarted, "candidate"), ready["encounter_id"], idempotency_key="retry"
        )
        == draft
    )


@pytest.mark.parametrize("quote_first", [False, True])
def test_preparing_second_intake_preserves_first_quote_and_acceptance(service, quote_first):
    inputs = setup_source(service)
    learner, first, _, _, _ = learn(service, inputs)
    registry = service.registry.manifest(first.source.corpus_id)
    a = compile_prepared_source(
        learner, learner.assess(first)["encounter_id"], idempotency_key="prepare-a"
    )
    early_quote = (
        service.issue_quote(
            first.request_id, QuoteRequest(expected_revision=a.revision, idempotency_key="quote")
        )
        if quote_first
        else None
    )
    second = make_case(service, inputs, "second")
    b = compile_prepared_source(
        learner, learner.assess(second)["encounter_id"], idempotency_key="prepare-b"
    )
    for case, draft in ((first, a), (second, b)):
        quote = service.issue_quote(
            case.request_id,
            QuoteRequest(expected_revision=draft.revision, idempotency_key="quote"),
        )
        if case == first and early_quote:
            assert quote == early_quote
        order = service.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id,
                customer_actor=CUSTOMER,
                idempotency_key="accept-" + case.request_id,
            )
        )
        assert order.authorization.status == "pending"
        assert fund(service, order).verification.passed
    assert service.registry.manifest(first.source.corpus_id) == registry


def test_preparation_key_rejects_changed_encounter(service):
    learner, case, _, _, _ = learn(service, setup_source(service))
    ready = learner.assess(case)
    other = learner.assess(case.model_copy(update={"case_id": "different"}))
    compile_prepared_source(learner, ready["encounter_id"], idempotency_key="same")
    with pytest.raises(DomainError, match="changed request"):
        compile_prepared_source(learner, other["encounter_id"], idempotency_key="same")


@pytest.mark.parametrize("stage", ["publish", "quote", "accept"])
@pytest.mark.parametrize("change", ["revoked", "expired"])
def test_prepared_sources_still_reject_authority_changes(service, stage, change):
    now = service.clock()
    if change == "expired":
        service.clock.now = now - timedelta(hours=2) + timedelta(seconds=30)
    inputs = setup_source(service)
    service.clock.now = now
    learner, case, _, _, _ = learn(service, inputs)
    ready = learner.assess(case)

    def invalidate():
        if change == "revoked":
            setup_source(service, head_version=2, status="revoked")
        else:
            # Expire only the authority, without first expiring intake/quote.
            service.clock.now += timedelta(seconds=30)

    if stage == "publish":
        invalidate()
        with pytest.raises((ValueError, DomainError)):
            compile_prepared_source(learner, ready["encounter_id"], idempotency_key="prep")
        return
    draft = compile_prepared_source(learner, ready["encounter_id"], idempotency_key="prep")
    command = QuoteRequest(expected_revision=draft.revision, idempotency_key="quote")
    quote = service.issue_quote(case.request_id, command) if stage == "accept" else None
    invalidate()
    with pytest.raises(DomainError, match="changed or expired"):
        if quote:
            service.accept_quote(
                AcceptQuoteCommand(
                    quote_id=quote.quote_id, customer_actor=CUSTOMER, idempotency_key="accept"
                )
            )
        else:
            service.issue_quote(case.request_id, command)
