"""Paid learning is a separately authorized local qualification, never a default."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.agents.budget import BudgetExceeded, ModelBudget
from app.main import create_app


def application(tmp_path, **extra):
    return create_app(
        tmp_path / "orders.db",
        artifact_root=tmp_path / "bytes",
        compiler=object(),  # Boundary tests make no SDK requests.
        run_worker=False,
        payment_mode="mock",
        source_learning=True,
        internal_token="worker",
        reviewer_token="reviewer",
        source_owner_token="owner",
        **extra,
    )


def configure(tmp_path, monkeypatch, *, expired=False):
    now = datetime.now(UTC)
    cutoff = now + timedelta(minutes=-1 if expired else 10)
    path = tmp_path / "budget.db"
    budget = ModelBudget(path, cutoff=(now - timedelta(hours=2)).isoformat())
    budget.register_authorized_window(
        "test-qualification",
        starts_at=(now - timedelta(minutes=20)).isoformat(),
        cutoff=cutoff.isoformat(),
        authorization_sha256="a" * 64,
    )
    for key, value in {
        "ENABLE_PAID_MODELS": "true",
        "ENABLE_DATASET_MODEL_ASSESSMENT": "true",
        "CLAUDE_MODEL": "claude-opus-5-5",
        "APPLICATION_MODEL_BUDGET_PATH": str(path),
        "APPLICATION_MODEL_WINDOW_ID": "test-qualification",
        "APPLICATION_MODEL_CUTOFF_AT": cutoff.isoformat(),
        "APPLICATION_MODEL_BUDGET_USD": "45",
        "APPLICATION_MODEL_CONCURRENCY": "1",
    }.items():
        monkeypatch.setenv(key, value)


def test_default_still_rejects_paid_learning(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_PAID_MODELS", "true")
    with pytest.raises(ValueError, match="forbids paid"):
        with TestClient(application(tmp_path)):
            pass


def test_explicit_opt_in_requires_open_registered_window(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, expired=True)
    with pytest.raises(BudgetExceeded, match="closed"):
        with TestClient(application(tmp_path, source_learning_model_qualification=True)):
            pass


def test_explicit_open_window_preserves_local_mock_boundary(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    with TestClient(application(tmp_path, source_learning_model_qualification=True)) as client:
        assert client.app.state.source_learning is not None
        assert client.app.state.orders.payments.mode == "mock"
        assert client.get("/source-learning/state").status_code == 403
        assert (
            client.get("/source-learning/state", headers={"X-Internal-Token": "worker"}).status_code
            == 200
        )


def test_opt_in_cannot_hide_disabled_investigator(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "false")
    with pytest.raises(ValueError, match="requires mock payments"):
        with TestClient(application(tmp_path, source_learning_model_qualification=True)):
            pass
