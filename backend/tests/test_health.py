from fastapi.testclient import TestClient

from app.main import create_app


def test_health_discloses_mock_mode(tmp_path):
    with TestClient(create_app(tmp_path / "health.sqlite3", run_worker=False)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "payment_mode": "mock",
        "live_settlement_enabled": False,
    }
