import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.integration.db_utils import db_available


def _set_debug_env(monkeypatch: pytest.MonkeyPatch, enabled: bool, token: str | None) -> None:
    monkeypatch.setenv("DEBUG_API_ENABLED", "1" if enabled else "0")
    if token is None:
        monkeypatch.delenv("DEBUG_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEBUG_API_TOKEN", token)


def _set_stub_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOVERY_COMPARE_SNAPSHOT_PROVIDER", "stub")
    monkeypatch.setenv("DISCOVERY_COMPARE_PRODUCT_CANDIDATE_PROVIDER", "stub")


def test_llm_runs_listing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.get("/v1/debug/llm-runs:by-run/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


def test_llm_runs_listing_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get("/v1/debug/llm-runs:by-run/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403


@pytest.mark.integration
def test_llm_runs_listing_and_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    _set_stub_providers(monkeypatch)

    client = TestClient(app)
    compare_resp = client.post("/v1/discovery/compare")
    assert compare_resp.status_code == 200
    run_id = compare_resp.json()["run_id"]

    list_resp = client.get(
        f"/v1/debug/llm-runs:by-run/{run_id}",
        headers={"X-Debug-Token": "secret"},
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["items"]

    item = payload["items"][0]
    assert "has_validation_errors" in item
    assert "validation_errors_count" in item

    detail_resp = client.get(
        f"/v1/debug/llm-runs/{item['id']}:detail",
        headers={"X-Debug-Token": "secret"},
    )
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert "prompt" in detail_payload
    assert "json_schema" in detail_payload
    assert isinstance(detail_payload["validation_errors"], list)
