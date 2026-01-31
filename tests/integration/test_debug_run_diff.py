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


def _create_run(client: TestClient) -> str:
    response = client.post("/v1/discovery/compare")
    assert response.status_code == 200
    payload = response.json()
    return payload["run_id"]


def test_debug_run_diff_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.get(
        "/v1/debug/compare-runs:diff?left_run_id=00000000-0000-0000-0000-000000000001&right_run_id=00000000-0000-0000-0000-000000000002"
    )
    assert response.status_code == 404


def test_debug_run_diff_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get(
        "/v1/debug/compare-runs:diff?left_run_id=00000000-0000-0000-0000-000000000001&right_run_id=00000000-0000-0000-0000-000000000002"
    )
    assert response.status_code == 403


def test_debug_run_diff_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get(
        "/v1/debug/compare-runs:diff?left_run_id=00000000-0000-0000-0000-000000000001&right_run_id=00000000-0000-0000-0000-000000000002",
        headers={"X-Debug-Token": "wrong"},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_debug_run_diff_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    _set_stub_providers(monkeypatch)

    client = TestClient(app)
    left_run_id = _create_run(client)
    right_run_id = _create_run(client)

    response = client.get(
        f"/v1/debug/compare-runs:diff?left_run_id={left_run_id}&right_run_id={right_run_id}",
        headers={"X-Debug-Token": "secret"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["left_run_id"] == left_run_id
    assert payload["right_run_id"] == right_run_id
    assert "phase_counts" in payload
    assert "left" in payload["phase_counts"]
    assert "right" in payload["phase_counts"]
    assert payload["timeline"]
    assert "refs" in payload
    assert "snapshots" in payload["refs"]
