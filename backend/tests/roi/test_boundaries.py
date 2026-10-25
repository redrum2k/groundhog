import json
import os
import re
import socket
import sys
from pathlib import Path

import anthropic
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.aggregate.execution import offline_guards
from evals.roi.plan import freeze
from evals.roi.report import render
from evals.roi.scoring import score


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


def test_public_snapshot_has_no_private_links_and_preserves_failed_cases(tmp_path):
    directory = tmp_path / "missing"
    freeze(directory, "0" * 40)
    observed = score(directory)
    original = (directory / "results.json").read_bytes()
    data = render(directory, "public.html", public_snapshot=True)
    assert data["summary"] == observed["summary"]
    assert not data["quality_gate"]
    assert len(data["cases"]) == 201
    assert all("trace" not in r and "process_id" not in r for r in data["cases"])
    page = (directory / "public.html").read_text(encoding="utf-8")
    assert "Public evidence snapshot" in page
    markup = page.split('<script id="roi-data"')[0]
    assert all(link.startswith("#") for link in re.findall(r'href="([^"]+)"', markup))
    assert (directory / "results.json").read_bytes() == original
    assert str(tmp_path) not in json.dumps(data)
    with pytest.raises(FileExistsError):
        render(directory, "public.html", public_snapshot=True)


def test_dashboard_has_no_network_or_financial_mutation_interface():
    root = Path(__file__).resolve().parents[3]
    script = (root / "evals/roi/dashboard.js").read_text(encoding="utf-8")
    template = (root / "evals/roi/dashboard.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in template and "form-action 'none'" in template
    assert not any(
        token in script
        for token in ("fetch(", "XMLHttpRequest", "WebSocket", "/api/", ".sendBeacon(")
    )


def test_committed_public_dashboard_matches_preserved_evidence():
    root = Path(__file__).resolve().parents[3]
    page = (root / "docs/evidence/roi-dashboard.html").read_text(encoding="utf-8")
    payload = page.split('<script id="roi-data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(payload)
    evidence = json.loads((root / "docs/evidence/roi-lab-20261025.json").read_text())
    assert data["source_commit"] == evidence["execution_commit"]
    assert data["capsule_sha256"] == evidence["capsule_sha256"]
    assert data["summary"] == evidence["summary"]
    assert data["assumptions"] == evidence["assumptions"]
    assert len(data["cases"]) == 201
    assert all("trace" not in r and "process_id" not in r for r in data["cases"])
    script = (root / "evals/roi/dashboard.js").read_text(encoding="utf-8")
    assert f"<script>{script}</script>" in page
