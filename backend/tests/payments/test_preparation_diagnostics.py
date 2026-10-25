import pytest

from app.payments.base_rpc import BaseTransportError
from app.payments.executor import FakeChainTransport, PaymentExecutor
from app.payments.journal import PaymentJournal
from tests.payments.test_journal import account, reserve


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            BaseTransportError("eth_getCode unavailable; inspect/reconcile before retrying"),
            "eth_getCode unavailable",
        ),
        (
            BaseTransportError("signer needs more ETH for gas and L1 fee margin"),
            "signer needs more ETH",
        ),
        (
            ValueError("secret-rpc-url private-buyer-capability"),
            "ValueError: transaction preparation failed before submission",
        ),
    ],
)
def test_safe_preparation_cause_is_saved_without_exposing_arbitrary_errors(
    tmp_path, error, expected
):
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    op = reserve(journal, account(), "void")

    class FailedPreparation(FakeChainTransport):
        def prepare_transaction(self, *args, **kwargs):
            raise error

    transport = FailedPreparation()
    result = PaymentExecutor(journal, transport).run_one(op.operation_id, broadcast=True)
    assert result.state == "failed"
    assert expected in result.error
    assert "secret-rpc-url" not in result.error and "private-buyer-capability" not in result.error
    assert not transport.broadcasts and not transport.signed and result.transaction_hash is None
    with journal.transaction() as db:
        assert journal.get(db, op.operation_id).error == result.error
