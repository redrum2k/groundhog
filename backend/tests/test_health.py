from fastapi.testclient import TestClient

from app.main import app


def test_health_discloses_mock_mode():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "payment_mode": "mock",
        "live_settlement_enabled": False,
    }
