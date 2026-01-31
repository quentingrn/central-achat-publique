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


def test_debug_snapshot_guard_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.get("/v1/debug/snapshots/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


def test_debug_snapshot_guard_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.post(
        "/v1/debug/snapshots:capture",
        json={"url": "https://example.com/snapshot", "provider": "stub"},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_debug_snapshot_capture_and_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)

    capture_resp = client.post(
        "/v1/debug/snapshots:capture",
        json={"url": "https://example.com/snapshot", "provider": "stub"},
        headers={"X-Debug-Token": "secret"},
    )
    assert capture_resp.status_code == 200
    capture_payload = capture_resp.json()
    snapshot_id = capture_payload["snapshot_id"]

    get_resp = client.get(
        f"/v1/debug/snapshots/{snapshot_id}",
        headers={"X-Debug-Token": "secret"},
    )
    assert get_resp.status_code == 200
    get_payload = get_resp.json()
    assert get_payload["item"]["snapshot_id"] == snapshot_id
    assert isinstance(get_payload["raw_extracted_json"], dict)
    assert isinstance(get_payload["item"]["missing_critical"], list)
    assert isinstance(get_payload["item"]["errors"], list)

    list_resp = client.get(
        "/v1/debug/snapshots:by-url",
        params={"url": "https://example.com/snapshot", "limit": 10},
        headers={"X-Debug-Token": "secret"},
    )
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["items"]
    assert list_payload["items"][0]["url"] == "https://example.com/snapshot"
