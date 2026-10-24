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
        "contract_version": "catalog-api-v1",
        "payment_policy": "catalog-payments-v1",
        "buyer_signature_validation": True,
        "mock_funding_requires_authorization": True,
        "live_adapter": "planned",
        "customer_authentication": False,
    }
