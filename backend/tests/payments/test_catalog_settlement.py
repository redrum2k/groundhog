"""Catalog + real SQLite + offline transport; no live adapter, RPC or paid calls."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from app.contracts.catalog import (
    AcceptQuoteCommand,
    CatalogOrder,
    Complaint,
    DisputeCommand,
    OfferCommand,
    QuoteRequest,
    RequestCommand,
    ReviewCommand,
    RevisionCommand,
)
from app.contracts.payments import FundingAuthorization
from app.orders.catalog import CatalogService
from app.orders.service import DomainError
from app.payments.base_config import BasePaymentConfig
from app.payments.catalog import MOCK_DOMAIN
from app.payments.executor import ChainObservation, FakeChainTransport
from app.payments.protocol import usdc_domain
from tests.catalog.fixtures import cmd, upload
from tests.payments.test_journal import observed


class CatalogChain(FakeChainTransport):
    def verified_usdc_domain(self):
        return usdc_domain("Synthetic verified USDC")


class Journey:
    def __init__(self, setup):
        original, self.clock, self.fixtures = setup
        self.buyer = Account.create()
        self.config = BasePaymentConfig(
            operator_private_key=Account.create().key.hex(),
            provider_address=Account.create().address,
        )
        self.chain = CatalogChain()
        self.service = CatalogService(
            original.repository,
            original.store.root,
            self.clock,
            payment_mode="base_sepolia",
            payment_config=self.config,
            payment_transport=self.chain,
        )

    def restart(self):
        self.service = CatalogService(
            self.service.repository,
            self.service.store.root,
            self.clock,
            payment_mode="base_sepolia",
            payment_config=self.config,
            payment_transport=self.chain,
        )

    def current(self, order):
        return self.service.get(order.snapshot.order_id)

    def view(self, order):
        return self.service.current_view(order.snapshot.order_id)

    def operation(self, order, action):
        with self.service.repository.transaction() as db:
            identifier = db.execute(
                "SELECT operation_id FROM payment_operations WHERE payment_id=? AND action=? "
                "ORDER BY rowid DESC LIMIT 1",
                (order.payment_id, action),
            ).fetchone()[0]
            return self.service.payments.journal.get(db, identifier)

    def accepted(self, key="request"):
        s = self.service
        draft = s.create_request(
            RequestCommand(
                prompt=(
                    "Find storage products with net unit weight under 2 kg "
                    "and unit price at most USD 40."
                ),
                corpus_id="storage-2026",
                idempotency_key=key,
            )
        )
        draft = s.compile_request(
            draft.request_id,
            RevisionCommand(
                expected_revision=draft.revision,
                idempotency_key="compile",
            ),
        )
        quote = s.issue_quote(
            draft.request_id,
            QuoteRequest(
                expected_revision=draft.revision,
                idempotency_key="quote",
                payer=self.buyer.address,
            ),
        )
        return s.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id,
                customer_actor="customer:test",
                idempotency_key=key,
            )
        )

    def authorize(self, order):
        s = self.service
        preparation = s.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
        signature = (
            "0x"
            + Account.sign_message(
                encode_typed_data(
                    full_message=preparation.typed_data.model_dump(mode="json", by_alias=True)
                ),
                self.buyer.key,
            ).signature.hex()
        )
        command = FundingAuthorization(
            **cmd(order, "fund").model_dump(),
            funding_attempt_id=preparation.funding_attempt_id,
            payment_hash=preparation.terms.payment_hash,
            signature=signature,
        )
        return s.payments.authorize(order.snapshot.order_id, command), command

    def confirm(self, order, action):
        operation = self.operation(order, action)
        self.chain.observations[operation.transaction_hash] = observed(
            operation, self.view(order).payment.payment
        )
        self.service.payments.work()
        return self.current(order)

    def funded(self):
        order, _ = self.authorize(self.accepted())
        self.service.payments.work()
        return self.confirm(order, "fund")

    def delivered(self):
        s = self.service
        order = s.run_one(self.funded().snapshot.order_id)
        order = upload(s, order, self.fixtures["repair"].artifact)
        s.run_one(order.snapshot.order_id)
        return s.run_one(order.snapshot.order_id)

    def capture(self, order):
        return self.service.mutate(order.snapshot.order_id, "accept", cmd(order, "accept"))

    def dispute(self, order):
        return self.service.mutate(
            order.snapshot.order_id,
            "dispute",
            cmd(
                order,
                "dispute",
                DisputeCommand,
                complaint=Complaint(
                    text="Check the weight against source evidence.",
                    product_id="S01",
                    field="weight",
                    requirement_id="R-WEIGHT",
                    artifact_id=order.deliveries[-1].pdf.artifact_id,
                ),
            ),
        )

    def release(self, order, key="release"):
        return self.service.mutate(
            order.snapshot.order_id,
            "review",
            cmd(
                order,
                key,
                ReviewCommand,
                action="release_authorization",
                reason="Required evidence remains unavailable.",
                supporting_evidence=(
                    (order.verification or order.verification_history[-1])
                    .assessments[0]
                    .citations[0],
                ),
            ),
            actor="reviewer:test",
        )

    def replacement(self):
        s = self.service
        parent = s.run_one(self.funded().snapshot.order_id)
        parent = upload(s, parent, self.fixtures["substantive"].artifact)
        parent = s.run_one(parent.snapshot.order_id)
        quote = s.offer(
            parent.snapshot.order_id,
            cmd(
                parent,
                "offer",
                OfferCommand,
                work_description="Use the proposed catalog facts.",
                terms=parent.snapshot.quote.specification.terms,
                amendment_id=parent.amendments[-1].amendment_id,
            ),
            actor="provider:test",
        )
        child = s.accept_quote(
            AcceptQuoteCommand(
                quote_id=quote.quote_id,
                customer_actor="customer:test",
                idempotency_key="child",
            )
        )
        return self.current(parent), child


@pytest.fixture
def journey(setup):
    return Journey(setup)


def test_funding_signature_submission_restart_and_exact_replay(journey):
    j = journey
    accepted = j.accepted()
    terms = accepted.snapshot.quote.payment_terms
    assert terms.amount_atomic == 15_000_000
    assert terms.payment_info.operator == j.config.operator_address
    assert terms.payment_info.receiver == j.config.provider_address
    pending, command = j.authorize(accepted)
    saved_view = j.service.command_view(pending, command.idempotency_key)
    assert pending.authorization.receipt is None
    with pytest.raises(DomainError, match="dispatch requires"):
        j.service.claim_job(pending.snapshot.order_id)
    j.service.payments.work()
    assert j.operation(pending, "fund").state == "submitted"
    assert j.current(pending).jobs[0].attempts == 0
    assert j.current(pending).authorization.receipt is None
    j.restart()
    funded = j.confirm(pending, "fund")
    assert funded.order_state == "processing" and len(funded.jobs) == 1
    assert funded.authorization.receipt.status == "confirmed"
    for _ in range(3):
        j.service.payments.work()
    assert j.service.payments.authorize(funded.snapshot.order_id, command) == pending
    assert j.service.command_view(pending, command.idempotency_key) == saved_view
    assert j.current(funded).snapshot.quote.payment_terms == terms
    with ThreadPoolExecutor(2) as pool:

        def claim(_):
            try:
                return j.service.claim_job(funded.snapshot.order_id)[1]
            except DomainError:
                return None

        jobs = list(pool.map(claim, range(2)))
    assert sum(job is not None for job in jobs) == 1
    assert len(j.chain.signed) == len(j.chain.broadcasts) == 1


def test_capture_pending_confirmation_atomic_and_once(journey, monkeypatch):
    j = journey
    delivered = j.delivered()
    assert not delivered.ledger and not j.operation(delivered, "fund").intent.action == "capture"
    pending = j.capture(delivered)
    assert j.view(pending).payment.payment.state == "capture_pending"
    assert pending.order_state == "delivered" and not pending.ledger
    assert "accept" not in j.view(pending).available_actions
    j.service.payments.work()
    assert not j.current(pending).ledger
    operation = j.operation(pending, "capture")
    j.chain.observations[operation.transaction_hash] = observed(
        operation, j.view(pending).payment.payment
    )
    original = j.service.repository.put

    def fail_booking(db, kind, key, value):
        if kind == "order" and value.ledger:
            raise RuntimeError("synthetic booking failure")
        return original(db, kind, key, value)

    monkeypatch.setattr(j.service.repository, "put", fail_booking)
    with pytest.raises(RuntimeError, match="booking failure"):
        j.service.payments.work()
    assert j.operation(pending, "capture").state == "submitted"
    assert not j.current(pending).ledger
    with j.service.repository.transaction() as db:
        assert (
            db.execute("SELECT count(*) FROM payment_effects WHERE kind='terminal'").fetchone()[0]
            == 0
        )
    monkeypatch.setattr(j.service.repository, "put", original)
    j.restart()
    captured = j.confirm(pending, "capture")
    assert captured.order_state == "closed" and len(captured.ledger) == 1
    for _ in range(3):
        j.service.payments.work()
    assert len(j.current(captured).ledger) == 1
    assert len(j.current(captured).deliveries) == 1
    assert j.view(captured).payment.payment.state == "captured"


def test_dispute_before_submission_invalidates_capture(journey):
    j = journey
    order = j.dispute(j.capture(j.delivered()))
    assert j.operation(order, "capture").state == "invalidated"
    j.service.payments.work()
    assert not order.ledger and len(j.chain.broadcasts) == 1
    assert j.view(order).payment.payment.state == "funded"
    assert order.cases[-1].status == "open"


def test_binding_change_during_signing_invalidates_and_allows_later_capture(journey):
    j = journey
    order = j.capture(j.delivered())
    original = j.chain.prepare_transaction

    def change(*args, **kwargs):
        with j.service.repository.transaction() as db:
            current = j.service.repository.load(db, "order", order.snapshot.order_id, CatalogOrder)
            j.service._invalidate(current)
            j.service._enqueue(current, "reverify")
            current.revision += 1
            j.service._save(db, current)
        return original(*args, **kwargs)

    j.chain.prepare_transaction = change
    j.service.payments.work()
    assert j.operation(order, "capture").state == "invalidated"
    assert len(j.chain.broadcasts) == 1
    j.chain.prepare_transaction = original
    current = j.service.run_one(order.snapshot.order_id)
    assert current.verification.passed
    new = j.service.mutate(current.snapshot.order_id, "accept", cmd(current, "accept-new"))
    j.service.payments.work()
    confirmed = j.confirm(new, "capture")
    assert len(confirmed.ledger) == 1 and len(confirmed.deliveries) == 1
    assert len([o for o in j.view(new).payment.operations if o.intent.action == "capture"]) == 2


def test_late_dispute_keeps_submitted_capture_and_human_resolution(journey):
    j = journey
    order = j.capture(j.delivered())
    j.service.payments.work()
    submitted = j.operation(order, "capture")
    j.clock.advance(61)
    assert "dispute" in j.view(order).available_actions
    order = j.dispute(j.current(order))
    assert order.order_state == "human_review" and order.cases[-1].status == "human_review"
    assert j.operation(order, "capture").transaction_hash == submitted.transaction_hash
    with pytest.raises(DomainError, match="terminal operation"):
        j.release(order)
    j.restart()
    confirmed = j.confirm(order, "capture")
    assert confirmed.order_state == "human_review" and len(confirmed.ledger) == 1
    assert j.view(confirmed).payment.payment.state == "captured"
    assert len(j.chain.broadcasts) == 2


@pytest.mark.parametrize(
    "change",
    [
        "missing_event",
        "wrong_event",
        "wrong_amount",
        "wrong_hash",
        "missing_state",
        "wrong_state",
        "wrong_block",
        "one_confirmation",
    ],
)
def test_missing_or_mismatched_confirmation_never_books(journey, change):
    j = journey
    order, _ = j.authorize(j.accepted())
    j.service.payments.work()
    operation = j.operation(order, "fund")
    evidence = observed(operation, j.view(order).payment.payment)
    if change == "missing_event":
        evidence = replace(evidence, event=None)
    elif change == "wrong_event":
        evidence = replace(evidence, event={**evidence.event, "name": "PaymentCaptured"})
    elif change == "wrong_amount":
        evidence = replace(evidence, event={**evidence.event, "amount_atomic": 100000})
    elif change == "wrong_hash":
        evidence = replace(evidence, event={**evidence.event, "payment_hash": "0x" + "0" * 64})
    elif change == "missing_state":
        evidence = replace(evidence, payment_state=None)
    elif change == "wrong_state":
        evidence = replace(
            evidence, payment_state={**evidence.payment_state, "capturable_amount": 0}
        )
    elif change == "wrong_block":
        evidence = replace(evidence, payment_state={**evidence.payment_state, "block_number": 99})
    else:
        evidence = replace(evidence, confirmations=1)
    j.chain.observations[operation.transaction_hash] = evidence
    j.service.payments.work()
    assert j.current(order).authorization.receipt is None
    assert j.operation(order, "fund").state in ("uncertain", "submitted")
    with pytest.raises(DomainError):
        j.service.claim_job(order.snapshot.order_id)


def test_ambiguous_submission_expiry_reconciles_same_operation(journey):
    j = journey
    order, _ = j.authorize(j.accepted())
    j.chain.broadcast_error = TimeoutError("do not expose capability")
    j.service.payments.work()
    operation = j.operation(order, "fund")
    assert operation.state == "uncertain"
    j.clock.advance(3601)
    j.restart()
    j.service.payments.work()
    funded = j.confirm(order, "fund")
    assert funded.order_state == "human_review"
    assert j.view(funded).payment.payment.state == "expired_not_returned"
    assert not funded.ledger
    assert len(j.chain.signed) == len(j.chain.broadcasts) == 1


@pytest.mark.parametrize("phase", ["fund", "capture"])
def test_reorg_preserves_financial_history_and_stops_work(journey, phase):
    j = journey
    order = j.funded() if phase == "fund" else j.capture(j.delivered())
    if phase == "capture":
        j.service.payments.work()
        order = j.confirm(order, phase)
    ledger = order.ledger
    operation = j.operation(order, phase)
    j.chain.observations[operation.transaction_hash] = replace(
        observed(operation, j.view(order).payment.payment),
        canonical=False,
    )
    # Explicit inspection bypasses the routine audit cadence.
    j.service.payments.executor.run_one(operation.operation_id)
    current = j.current(order)
    assert current.ledger == ledger and current.order_state == "human_review"
    assert j.view(order).payment.payment.state == "reorg_hold"
    with pytest.raises(DomainError):
        j.service.claim_job(order.snapshot.order_id)
    j.restart()
    j.service.payments.work()
    assert j.current(order).ledger == ledger
    assert len(j.chain.broadcasts) == (1 if phase == "fund" else 2)


@pytest.mark.parametrize("outcome", ["pending", "uncertain", "failed"])
def test_replacement_waits_for_confirmed_parent_return(journey, outcome):
    j = journey
    parent, child = j.replacement()
    assert not parent.ledger and parent.order_state != "closed"
    assert j.view(child).payment.payment.state == "blocked_parent"
    assert not j.view(child).available_actions
    j.service.payments.work()
    operation = j.operation(parent, "void")
    j.chain.observations[operation.transaction_hash] = ChainObservation(
        outcome,
        block_number=100,
        block_hash="0x" + "a" * 64,
        confirmations=2,
        canonical=True,
    )
    j.service.payments.work()
    j.restart()
    assert not j.current(parent).ledger
    with pytest.raises(DomainError):
        j.service.payments.prepare(child.snapshot.order_id, cmd(j.current(child), "blocked"))
    with pytest.raises(DomainError):
        j.service.claim_job(child.snapshot.order_id)
    if outcome == "failed":
        # A definitive reverted transaction needs a new explicit reviewer decision.
        parent = j.release(j.current(parent), "retry-return")
        j.service.payments.work()
    returned = j.confirm(parent, "void")
    assert len(returned.ledger) == 1 and returned.order_state == "closed"
    child = j.current(child)
    assert j.view(child).payment.payment.state == "awaiting_signature"
    assert child.snapshot.quote.payment_terms.amount_atomic == 5_000_000
    assert child.snapshot.quote.payment_terms.payment_id != parent.payment_id
    child, _ = j.authorize(child)
    assert child.jobs[0].attempts == 0
    j.service.payments.work()
    child = j.confirm(child, "fund")
    assert j.service.run_one(child.snapshot.order_id).verification.passed


def test_base_requires_configuration_payer_and_verified_domain(journey):
    j = journey
    with pytest.raises(ValueError, match="explicit configuration"):
        CatalogService(j.service.repository, j.service.store.root, payment_mode="base_sepolia")
    with pytest.raises(DomainError, match="explicit payer"):
        j.service.payments.terms(j.service.price("initial"), None, j.clock())
    order = j.accepted()
    j.chain.verified_usdc_domain = lambda: MOCK_DOMAIN
    with pytest.raises(DomainError, match="verified Base token domain"):
        j.service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
    assert not j.chain.signed and not j.chain.broadcasts


@pytest.mark.parametrize("changed", ["expiry", "verification", "amount", "authority", "consent"])
def test_current_capture_gates_rechecked_before_submission(journey, changed):
    from app.contracts.catalog import Approval

    j = journey
    order = j.capture(j.delivered())
    with j.service.repository.transaction() as db:
        if changed == "expiry":
            j.clock.advance(3600)
        elif changed == "verification":
            order.verification = None
        elif changed == "amount":
            order.authorization = order.authorization.model_copy(
                update={
                    "amount": order.authorization.amount.model_copy(update={"amount_minor": 10})
                }
            )
        elif changed == "authority":
            order.authority_state = "pending_source_authority"
        else:
            order.approvals = (
                Approval(
                    approval_id="consent",
                    reason="Synthetic outstanding customer/provider approval",
                    amendment_id="synthetic-amendment",
                    binding=order.binding,
                ),
            )
        # Persist the concurrent state directly to exercise the executor guard itself.
        j.service.repository.put(db, "order", order.snapshot.order_id, order)
    j.service.payments.work()
    assert j.operation(order, "capture").state == "invalidated"
    assert len(j.chain.broadcasts) == 1
    assert not j.current(order).ledger
    assert "accept" not in j.view(order).available_actions
    if changed == "expiry":
        assert j.view(order).payment.payment.state == "expired_not_returned"


def test_unsigned_and_reserved_funding_expire_without_work(journey):
    j = journey
    order, _ = j.authorize(j.accepted())
    terms = order.snapshot.quote.payment_terms
    j.clock.advance(181)
    j.service.payments.work()
    assert j.operation(order, "fund").state == "invalidated"
    assert j.view(order).payment.payment.state == "failed"
    assert j.current(order).snapshot.quote.payment_terms == terms
    assert j.current(order).jobs[0].attempts == 0
    assert not j.chain.broadcasts
    assert not j.view(order).available_actions


def test_undisputed_review_expiry_reserves_capture_but_never_books(journey):
    j = journey
    delivered = j.delivered()
    j.clock.advance(60)
    pending = j.current(delivered)
    assert pending.customer_acceptance is None
    assert not pending.ledger and pending.order_state == "delivered"
    assert j.view(pending).payment.payment.state == "capture_pending"
    j.service.payments.work()
    assert not j.current(pending).ledger
    assert j.confirm(pending, "capture").order_state == "closed"


def test_replacement_deadline_never_extends_while_waiting_for_parent(journey):
    j = journey
    parent, child = j.replacement()
    terms = child.snapshot.quote.payment_terms
    j.service.payments.work()
    j.clock.advance(181)
    j.confirm(parent, "void")
    child = j.current(child)
    assert j.view(child).payment.payment.state == "failed"
    assert child.order_state == "human_review" and child.snapshot.quote.payment_terms == terms
    assert child.jobs[0].attempts == 0


def test_parent_reorg_blocks_unsubmitted_child_funding_and_work(journey):
    j = journey
    parent, child = j.replacement()
    j.service.payments.work()
    j.confirm(parent, "void")
    child, _ = j.authorize(j.current(child))
    operation = j.operation(parent, "void")
    j.chain.observations[operation.transaction_hash] = replace(
        observed(operation, j.view(parent).payment.payment),
        canonical=False,
    )
    j.service.payments.executor.run_one(operation.operation_id)
    assert not j.view(child).available_actions
    j.service.payments.work()
    assert j.operation(child, "fund").state == "invalidated"
    assert not j.current(child).authorization.receipt
    with pytest.raises(DomainError):
        j.service.claim_job(child.snapshot.order_id)


def test_additional_work_has_independent_payment_without_parent_void(journey):
    j = journey
    parent = j.delivered()
    quote = j.service.offer(
        parent.snapshot.order_id,
        cmd(
            parent,
            "additional",
            OfferCommand,
            work_description="Make a shipping-weight shortlist.",
            terms=parent.snapshot.quote.specification.terms.model_copy(
                update={"weight_concept": "shipping"}
            ),
        ),
        actor="provider:test",
    )
    child = j.service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id,
            customer_actor="customer:test",
            idempotency_key="additional",
        )
    )
    assert j.view(child).payment.payment.state == "awaiting_signature"
    assert child.snapshot.quote.payment_terms.amount_atomic == 5_000_000
    assert child.authorization.authorization_id != parent.authorization.authorization_id
    assert not any(o.intent.action == "void" for o in j.view(parent).payment.operations)
    assert not j.current(parent).ledger


def test_historical_mock_records_and_saved_responses_survive_live_injection(setup):
    from tests.catalog.fixtures import repaired

    service, _, fixtures = setup
    order = repaired(service, fixtures)
    order = service.mutate(order.snapshot.order_id, "accept", cmd(order, "accept"))
    with service.repository.transaction() as db:
        records = db.execute("SELECT * FROM catalog_records ORDER BY kind,id").fetchall()
        commands = db.execute("SELECT * FROM catalog_commands ORDER BY scope,key").fetchall()
        effects = db.execute("SELECT * FROM payment_effects ORDER BY payment_id,kind").fetchall()
    j = Journey(setup)
    assert j.current(order) == order
    assert j.service.command_view(order, "accept").payment.simulated
    assert (
        j.service.mutate(
            order.snapshot.order_id,
            "accept",
            cmd(order.model_copy(update={"revision": order.revision - 1}), "accept"),
        )
        == order
    )
    j.service.payments.work()
    with service.repository.transaction() as db:
        assert db.execute("SELECT * FROM catalog_records ORDER BY kind,id").fetchall() == records
        assert (
            db.execute("SELECT * FROM catalog_commands ORDER BY scope,key").fetchall() == commands
        )
        assert (
            db.execute("SELECT * FROM payment_effects ORDER BY payment_id,kind").fetchall()
            == effects
        )


def test_capture_and_void_compete_atomically_in_catalog(journey):
    from app.contracts.catalog import ReviewerDecision

    j = journey
    order = j.delivered()
    order.customer_acceptance = order.binding
    order.decisions = (
        ReviewerDecision(
            actor="reviewer:test",
            action="release_authorization",
            reason="Synthetic release authority",
            supporting_evidence=(order.verification.assessments[0].citations[0],),
            binding=order.binding,
            recorded_at=j.clock(),
        ),
    )
    with j.service.repository.transaction() as db:
        j.service._save(db, order)

    def reserve(action):
        try:
            with j.service.repository.transaction() as db:
                current = j.service.repository.load(
                    db, "order", order.snapshot.order_id, CatalogOrder
                )
                j.service.payments.reserve_terminal(db, current, action)
                j.service._save(db, current)
            return action
        except DomainError as error:
            return error.status

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(reserve, ("capture", "void")))
    assert results.count(409) == 1
    assert not j.current(order).ledger
    j.service.payments.work()
    action = next(result for result in results if result != 409)
    confirmed = j.confirm(order, action)
    assert len(confirmed.ledger) == 1
    assert len(j.chain.broadcasts) == 2


def test_domain_verification_outside_lock_signature_binding_and_replay(journey):
    j = journey
    order = j.accepted()

    def domain():
        with j.service.repository.transaction() as db:
            assert j.service.payments.journal.payment(db, order.payment_id)
        return usdc_domain("Synthetic verified USDC")

    j.chain.verified_usdc_domain = domain
    preparation = j.service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare"))
    wrong_data = preparation.typed_data.model_dump(mode="json", by_alias=True)
    wrong_data["domain"] = MOCK_DOMAIN
    signature = (
        "0x"
        + Account.sign_message(
            encode_typed_data(full_message=wrong_data), j.buyer.key
        ).signature.hex()
    )
    command = FundingAuthorization(
        **cmd(order, "wrong-domain").model_dump(),
        funding_attempt_id=preparation.funding_attempt_id,
        payment_hash=preparation.terms.payment_hash,
        signature=signature,
    )
    with pytest.raises(DomainError, match="accepted payer") as error:
        j.service.payments.authorize(order.snapshot.order_id, command)
    assert error.value.status == 422 and signature not in str(error.value)
    with pytest.raises(DomainError, match="only mock"):
        j.service.payments.authorize(
            order.snapshot.order_id,
            command.model_copy(
                update={
                    "idempotency_key": "simulate",
                    "signature": None,
                    "simulate": True,
                }
            ),
        )
    j.chain.verified_usdc_domain = lambda: (_ for _ in ()).throw(RuntimeError("unavailable"))
    assert j.service.payments.prepare(order.snapshot.order_id, cmd(order, "prepare")) == preparation
    pending, _ = j.authorize(order)
    assert pending.authorization.receipt is None
    assert j.service.payments.work(limit=0).processed == 0
    with pytest.raises(ValueError, match="limit"):
        j.service.payments.work(limit=-1)


def test_funding_audit_cannot_overwrite_concurrent_capture_reservation(journey):
    j = journey
    order = j.delivered()
    operation = j.operation(order, "fund")
    original = j.chain.reconcile

    def reconcile(*args):
        j.capture(j.current(order))
        return original(*args)

    j.chain.reconcile = reconcile
    j.service.payments.executor.run_one(operation.operation_id)
    assert j.view(order).payment.payment.state == "capture_pending"
    assert "accept" not in j.view(order).available_actions
    assert not j.current(order).ledger


def test_uncertain_capture_recovers_exact_operation_and_preserves_booking(journey):
    j = journey
    order = j.capture(j.delivered())
    j.chain.broadcast_error = TimeoutError("possibly broadcast")
    j.service.payments.work()
    operation = j.operation(order, "capture")
    assert operation.state == "uncertain" and not j.current(order).ledger
    j.restart()
    confirmed = j.confirm(order, "capture")
    assert confirmed.authorization.status == "authorized"
    assert len(confirmed.ledger) == 1
    ledger = confirmed.ledger
    j.chain.observations[operation.transaction_hash] = ChainObservation("pending")
    j.service.payments.executor.run_one(operation.operation_id)
    assert j.current(order).ledger == ledger
    assert j.view(order).payment.payment.state == "uncertain"
    j.confirm(order, "capture")
    assert j.current(order).ledger == ledger
    assert j.current(order).authorization.status == "authorized"
    assert j.view(order).payment.payment.state == "captured"
    assert len(j.chain.broadcasts) == 2


def test_parent_return_reorg_blocks_delivered_child_at_review_expiry(journey):
    j = journey
    parent, child = j.replacement()
    j.service.payments.work()
    j.confirm(parent, "void")
    child, _ = j.authorize(j.current(child))
    j.service.payments.work()
    j.confirm(child, "fund")
    child = j.service.run_one(child.snapshot.order_id)
    assert child.verification.passed and child.order_state == "delivered"
    operation = j.operation(parent, "void")
    j.chain.observations[operation.transaction_hash] = replace(
        observed(operation, j.view(parent).payment.payment),
        canonical=False,
    )
    j.service.payments.executor.run_one(operation.operation_id)
    j.clock.advance(60)
    child = j.current(child)
    assert child.order_state == "human_review" and not child.ledger
    assert not j.view(child).available_actions
