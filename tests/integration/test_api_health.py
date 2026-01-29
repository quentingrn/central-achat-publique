from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compare_endpoint_exists() -> None:
    response = client.post("/v1/discovery/compare")
    assert response.status_code == 501
