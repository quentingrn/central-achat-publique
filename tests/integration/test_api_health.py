import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.integration.db_utils import db_available

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_compare_endpoint_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")
    monkeypatch.setenv("DISCOVERY_COMPARE_SNAPSHOT_PROVIDER", "stub")
    monkeypatch.setenv("DISCOVERY_COMPARE_PRODUCT_CANDIDATE_PROVIDER", "stub")
    response = client.post("/v1/discovery/compare")
    assert response.status_code == 200
    assert "run_id" in response.json()
    body = response.json()
    assert "run_id" in body
