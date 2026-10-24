"""Real HttpRpc, loopback HTTP only, with bounded scaled wall-clock deadlines."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from subprocess import Popen
from threading import Event, Thread

import pytest
from test_base_transport import buyer_signature, lab

from app.payments import base_rpc
from app.payments.attempt import AttemptStopped, PaymentAttempt
from app.payments.base import BasePaymentTransport
from app.payments.base_rpc import BaseTransportError, HttpRpc
from app.payments.journal import PaymentJournal

# isort: split
from spikes.payments.offline import BUYER_KEY, OfflineRpc, offline_config


@pytest.fixture
def endpoint():
    class Endpoint:
        mode = "stream"
        requests = []
        entered = Event()
        closed = Event()
        finish = Event()
        result = "0x14a34"

    state = Endpoint()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append(request)
            state.entered.set()
            body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": state.result})
            if state.mode == "rpc_error":
                body = json.dumps({"id": 1, "error": "secret-url raw-private-capability"})
            try:
                if state.mode == "headers":
                    state.finish.wait(0.6)
                self.send_response(302 if state.mode == "redirect" else 200)
                self.send_header("Location", "/must-not-retry")
                self.send_header(
                    "Content-Length", str(len(body) + (20 if state.mode == "stream" else 0))
                )
                self.end_headers()
                if state.mode == "stream":
                    for _ in range(20):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        if state.finish.wait(0.03):
                            return
                self.wfile.write(body.encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                state.closed.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}/secret-url"
    try:
        yield state
    finally:
        state.finish.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
        assert not thread.is_alive()


@pytest.fixture
def children(monkeypatch):
    children = []
    popen = base_rpc.subprocess.Popen

    def tracked(*args, **kwargs):
        process = popen(*args, **kwargs)
        children.append(process)
        assert kwargs["env"] == {} and kwargs["close_fds"]
        assert "secret-url" not in str(args)
        return process

    monkeypatch.setattr(base_rpc.subprocess, "Popen", tracked)
    yield children
    assert children
    assert all(child.poll() is not None for child in children)
    assert all(child.stdin.closed and child.stdout.closed for child in children)


@pytest.mark.parametrize("mode", ["stream", "headers"])
def test_http_total_limit_stops_stream_and_waiting_for_headers(endpoint, children, tmp_path, mode):
    endpoint.mode = mode
    transport = BasePaymentTransport(
        offline_config(tmp_path / "unused.sqlite3"), rpc=HttpRpc(endpoint.url, timeout=0.1)
    )
    start = time.monotonic()
    with PaymentAttempt(0.25).scope(), pytest.raises(AttemptStopped, match="HTTP elapsed"):
        transport._rpc("eth_chainId", [])
    elapsed = time.monotonic() - start
    assert endpoint.entered.is_set()  # Must exercise HTTP, not just process startup.
    assert len(endpoint.requests) == 1
    assert elapsed < 0.45  # Generous scheduling tolerance; old stream takes >0.6s.
    assert children[0].poll() is not None  # Reaped before caller regains control.


@pytest.mark.parametrize("mode", ["success", "rpc_error", "redirect"])
def test_http_success_errors_redaction_no_retry_and_cleanup(endpoint, children, mode):
    endpoint.mode = mode
    rpc = HttpRpc(endpoint.url, timeout=0.5)
    if mode == "success":
        assert rpc.request("eth_chainId", []) == "0x14a34"
    else:
        with pytest.raises(BaseTransportError) as error:
            rpc.request("eth_sendRawTransaction", ["raw-private-capability"])
        assert "secret-url" not in str(error.value)
        assert "capability" not in str(error.value)
        assert error.value.__suppress_context__
    assert len(endpoint.requests) == len(children) == 1


def test_cancellation_kills_http_before_return_and_cannot_deliver_late_result(endpoint, children):
    attempt = PaymentAttempt(1)
    rpc = HttpRpc(endpoint.url, timeout=0.5)
    results = []

    def call():
        with attempt.scope():
            results.append(rpc.request("eth_chainId", []))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(call)
        assert endpoint.entered.wait(1)
        attempt.cancelled.set()
        with pytest.raises(AttemptStopped, match="cancelled"):
            future.result(timeout=1)
        assert children[0].poll() is not None
        assert endpoint.closed.wait(1)  # Server sees closed socket while still streaming.
    assert results == [] and len(endpoint.requests) == 1


@pytest.mark.parametrize("stop", ["budget", "financial"])
def test_injected_deadline_during_http_stops_and_reaps(endpoint, children, stop):
    clock = [0.0]
    authority = [10.0]
    attempt = PaymentAttempt(1, clock=lambda: clock[0])
    attempt.configure("fund", None, remaining_authority=lambda: authority[0])

    def call():
        with attempt.scope():
            return HttpRpc(endpoint.url, timeout=0.5).request("eth_chainId", [])

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(call)
        assert endpoint.entered.wait(1)
        if stop == "budget":
            clock[0] = 1
        else:
            authority[0] = 0
        with pytest.raises(AttemptStopped):
            future.result(timeout=1)
        assert children[0].poll() is not None
    assert len(endpoint.requests) == 1


def test_process_interruption_also_reaps_request(endpoint, children, monkeypatch):
    class Interruption(BaseException):
        pass

    communicate = Popen.communicate

    def interrupted(process, *args, **kwargs):
        try:
            return communicate(process, *args, **kwargs)
        except base_rpc.subprocess.TimeoutExpired:
            if endpoint.entered.is_set():
                raise Interruption from None
            raise

    # children wraps the constructor; patch the actual process class, not the wrapper.
    monkeypatch.setattr(Popen, "communicate", interrupted)
    with pytest.raises(Interruption):
        HttpRpc(endpoint.url, timeout=0.5).request("eth_chainId", [])
    assert children[0].poll() is not None and len(endpoint.requests) == 1


@pytest.mark.parametrize("window", ["elapsed", "financial", "inspection"])
def test_actual_http_allowance_is_reserved_before_launch(endpoint, monkeypatch, window):
    clock = [0.0]
    attempt = PaymentAttempt(1, clock=lambda: clock[0])
    if window != "elapsed":
        attempt.configure(
            "fund", None, inspection=window == "inspection", remaining_authority=lambda: 0
        )
    else:
        clock[0] = 0.5
    rpc = HttpRpc(endpoint.url, timeout=0.5)
    if window == "inspection":
        endpoint.mode = "success"
        with attempt.scope():
            assert rpc.request("eth_getTransactionReceipt", ["synthetic"]) == "0x14a34"
    else:
        monkeypatch.setattr(base_rpc.subprocess, "Popen", lambda *a, **k: pytest.fail("launched"))
        with attempt.scope(), pytest.raises(AttemptStopped):
            rpc.request("eth_chainId", [])
        assert endpoint.requests == []


def test_ambiguous_http_send_retains_durable_identity_and_only_reconciles(
    endpoint, children, tmp_path
):
    config = offline_config(tmp_path / "lab.sqlite3", signing=True)
    rpc = OfflineRpc()
    payment = lab.create_fixture(
        config, "capture-a", lab.Account.from_key(BUYER_KEY).address, 1000, 3600, offline=True
    )
    journal = PaymentJournal(config.journal_path)
    operation = lab.operation_for(payment, "fund")
    with journal.transaction() as db:
        journal.create_payment(db, payment)
        journal.reserve(db, operation, "0x" + buyer_signature(payment.terms).hex())
    http = HttpRpc(endpoint.url, timeout=0.2)
    offline_request = rpc.request

    def request(method, params):
        if method == "eth_sendRawTransaction":
            # All preparation remains synthetic. The final POST uses real HttpRpc.
            return http.request(method, params)
        return offline_request(method, params)

    rpc.request = request
    worker = lab.laboratory_executor(journal, BasePaymentTransport(config, rpc=rpc))
    result = worker.run_one(operation.operation_id, broadcast=True)
    assert result.state == "submitted" and result.nonce == 0
    assert len(endpoint.requests) == len(children) == 1
    assert endpoint.requests[0]["method"] == "eth_sendRawTransaction"
    with journal.transaction() as db:
        saved = journal.private(db, operation.operation_id)
        assert saved[0] is not None and saved[1] is not None
        assert journal.payment(db, payment.payment_id).state == "funding_pending"
        assert db.execute("SELECT count(*) FROM payment_effects").fetchone()[0] == 0
    rpc.timestamp = 5000  # Financial expiry must not disable receipt inspection.
    result = worker.run_one(operation.operation_id, broadcast=True)
    assert result.state == "submitted" and result.nonce == 0
    with journal.transaction() as db:
        assert journal.private(db, operation.operation_id) == saved
        assert len(journal.operations(db, payment.payment_id)) == 1
    assert len(endpoint.requests) == 1 and not rpc.broadcasts
