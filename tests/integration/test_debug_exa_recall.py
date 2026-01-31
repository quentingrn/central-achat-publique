import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


def _set_debug_env(monkeypatch: pytest.MonkeyPatch, enabled: bool, token: str | None) -> None:
    monkeypatch.setenv("DEBUG_API_ENABLED", "1" if enabled else "0")
    if token is None:
        monkeypatch.delenv("DEBUG_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEBUG_API_TOKEN", token)


def test_debug_exa_recall_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.post("/v1/debug/recall/exa", json={"query": "laptop"})
    assert response.status_code == 404


def test_debug_exa_recall_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.post("/v1/debug/recall/exa", json={"query": "laptop"})
    assert response.status_code == 403


def test_debug_exa_recall_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    monkeypatch.setenv("EXA_MCP_URL", "stub")

    client = TestClient(app)
    response = client.post(
        "/v1/debug/recall/exa",
        json={"query": "laptop", "num_results": 3},
        headers={"X-Debug-Token": "secret"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "exa"
    assert len(payload["items"]) == 3
    assert payload["metrics"]["unique_domains_count"] == 2
    assert payload["metrics"]["has_duplicate_urls"] is True
    assert payload["metrics"]["top_domains"][0]["domain"] == "example.com"
