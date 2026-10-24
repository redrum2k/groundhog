"""Aggregate cutoff is enforced inside the real transport after executor checks."""

from dataclasses import replace

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from app.payments.base import BasePaymentTransport
from app.payments.protocol import receive_authorization_typed_data, usdc_domain
from app.runtime.dataset_policy import cutoff
from tests.dataset.conftest import accepted
from tests.payments.test_base_transport import lab  # noqa: F401 -- enables isolated lab import
from tests.payments.test_catalog_settlement import Journey

# isort: split
from spikes.payments.offline import OfflineRpc


@pytest.mark.parametrize("boundary", ["sign", "send"])
def test_latest_safe_submission_cutoff_inside_slow_transport(dataset_service, boundary):
    service, clock = dataset_service
    journey = Journey((service, clock, {}))
    service = journey.service
    order = accepted(service, payer=journey.buyer.address)
    order, _ = journey.authorize(order)
    service.payments.work()
    order = journey.confirm(order, "fund")
    order = service.run_one(order.snapshot.order_id)
    order = journey.capture(order)
    operation = journey.operation(order, "capture")
    terms = order.snapshot.quote.payment_terms
    original_snapshot = order.snapshot.model_dump_json()
    rpc = OfflineRpc(timestamp=int(clock().timestamp()))
    transport = BasePaymentTransport(
        replace(journey.config, enable_testnet_broadcast=True), rpc=rpc
    )
    signature = Account.sign_message(
        encode_typed_data(
            full_message=receive_authorization_typed_data(terms, usdc_domain("USDC"))
        ),
        journey.buyer.key,
    ).signature
    # Synthetic chain custody matching accepted terms, not a runtime funding shortcut.
    signed = transport.prepare_transaction("fund", terms, 0, bytes(signature))
    rpc.mine(signed.raw_transaction)
    journal = service.payments.journal
    request = rpc.request

    def delayed(method, params):
        trigger = method == "eth_getBalance" and params[1] == "pending"
        if boundary == "send":
            with journal.transaction() as db:
                trigger = journal.get(db, operation.operation_id).state == "submitted"
        if trigger:
            clock.advance((cutoff(order) - clock()).total_seconds())
        return request(method, params)

    rpc.request = delayed
    service.payments.executor.transport = transport
    result = service.payments.executor.run_one(operation.operation_id, broadcast=True)
    assert result.state == ("invalidated" if boundary == "sign" else "submitted")
    assert "cutoff" in result.error
    assert clock() == cutoff(order) < order.authorization.expires_at
    assert not rpc.broadcasts
    current = journey.current(order)
    assert current.snapshot.model_dump_json() == original_snapshot and not current.ledger
    with journal.transaction() as db:
        assert not any(
            op.intent.action == "void" for op in journal.operations(db, order.payment_id)
        )
    if boundary == "send":
        # This durable-but-unsent gap remains pending; ordinary reconciliation never sends.
        rpc.request = request
        clock.advance(121)
        for _ in range(2):
            inspected = service.payments.executor.run_one(operation.operation_id)
            assert inspected.state == "submitted" and inspected.nonce == result.nonce
            assert inspected.transaction_hash == result.transaction_hash
        assert not rpc.broadcasts and not journey.current(order).ledger
