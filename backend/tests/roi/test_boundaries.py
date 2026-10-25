import os
import socket
import sys
from pathlib import Path

import anthropic
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.aggregate.execution import offline_guards
from evals.roi.report import render


def test_existing_credentials_or_flags_cannot_enable_roi_spending(monkeypatch):
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-unusable-test-key")
    with offline_guards():
        assert os.environ["ENABLE_PAID_MODELS"] == "false"
        assert os.environ["PAYMENT_ADAPTER"] == "mock"
        assert "ANTHROPIC_API_KEY" not in os.environ
        with pytest.raises(RuntimeError, match="forbids"):
            anthropic.Anthropic()
        with pytest.raises(RuntimeError, match="forbids"):
            socket.getaddrinfo("example.com", 443)


def test_report_cannot_write_another_directory(tmp_path):
    with pytest.raises(ValueError, match="filename"):
        render(tmp_path, "../outside.html")


def test_dashboard_has_no_network_or_financial_mutation_interface():
    root = Path(__file__).resolve().parents[3]
    script = (root / "evals/roi/dashboard.js").read_text(encoding="utf-8")
    template = (root / "evals/roi/dashboard.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in template and "form-action 'none'" in template
    assert not any(
        token in script
        for token in ("fetch(", "XMLHttpRequest", "WebSocket", "/api/", ".sendBeacon(")
    )
