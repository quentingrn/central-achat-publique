from urllib.parse import quote

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


def test_debug_run_listing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.get("/v1/debug/compare-runs")
    assert response.status_code == 404


def test_debug_run_listing_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get("/v1/debug/compare-runs")
    assert response.status_code == 403


def test_debug_run_listing_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get(
        "/v1/debug/compare-runs",
        headers={"X-Debug-Token": "wrong"},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_debug_run_listing_pagination_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    _set_stub_providers(monkeypatch)

    client = TestClient(app)
    response_1 = client.post("/v1/discovery/compare")
    response_2 = client.post("/v1/discovery/compare")
    assert response_1.status_code == 200
    assert response_2.status_code == 200

    list_resp = client.get(
        "/v1/debug/compare-runs?limit=1",
        headers={"X-Debug-Token": "secret"},
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert len(payload["items"]) == 1
    assert payload["next_cursor"]

    cursor = quote(payload["next_cursor"])
    list_resp_2 = client.get(
        f"/v1/debug/compare-runs?limit=1&cursor={cursor}",
        headers={"X-Debug-Token": "secret"},
    )
    assert list_resp_2.status_code == 200
    payload_2 = list_resp_2.json()
    assert len(payload_2["items"]) == 1

    run_id = payload["items"][0]["run_id"]
    summary_resp = client.get(
        f"/v1/debug/compare-runs/{run_id}:summary",
        headers={"X-Debug-Token": "secret"},
    )
    assert summary_resp.status_code == 200
    summary_payload = summary_resp.json()
    assert summary_payload["item"]["run_id"] == run_id
    assert summary_payload["timeline"]
    assert "refs" in summary_payload
