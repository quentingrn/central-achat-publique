import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from modules.discovery_compare.adapters.schemas import PhaseNameV1
from modules.discovery_compare.application.run_recorder import RunRecorder
from modules.discovery_compare.infrastructure.persistence.models import PageSnapshot, Product
from shared.db.session import get_session
from tests.integration.db_utils import db_available


def _set_debug_env(monkeypatch: pytest.MonkeyPatch, enabled: bool, token: str | None) -> None:
    monkeypatch.setenv("DEBUG_API_ENABLED", "1" if enabled else "0")
    if token is None:
        monkeypatch.delenv("DEBUG_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEBUG_API_TOKEN", token)


def test_debug_guard_disabled_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.get(f"/v1/debug/compare-runs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_debug_guard_enabled_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get(f"/v1/debug/compare-runs/{uuid.uuid4()}")
    assert response.status_code == 403


def test_debug_guard_enabled_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.get(
        f"/v1/debug/compare-runs/{uuid.uuid4()}",
        headers={"X-Debug-Token": "wrong"},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_debug_endpoints_run_and_event(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    session = get_session()
    recorder = RunRecorder(session)
    try:
        run = recorder.create_run(source_url="https://example.com/p")
        recorder.add_event(run.id, PhaseNameV1.source_snapshot_capture.value, "ok")
        run_id = run.id
    finally:
        session.close()

    client = TestClient(app)
    response = client.get(
        f"/v1/debug/compare-runs/{run_id}",
        headers={"X-Debug-Token": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["events"][0]["phase_name"] == PhaseNameV1.source_snapshot_capture.value


@pytest.mark.integration
def test_debug_endpoints_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    session = get_session()
    recorder = RunRecorder(session)
    try:
        run = recorder.create_run(source_url="https://example.com/p")
        prompt = recorder.add_prompt("compare", "v1", "stub")
        tool_run = recorder.add_tool_run(run.id, "snapshot", "ok", {"in": 1}, {"out": 1})
        llm_run = recorder.add_llm_run(run.id, "mistral", "ok", prompt_id=prompt.id)
        prompt_id = prompt.id
        tool_run_id = tool_run.id
        llm_run_id = llm_run.id

        product = Product(brand="ACME", model="X1")
        session.add(product)
        session.commit()
        session.refresh(product)

        snapshot = PageSnapshot(
            product_id=product.id,
            url=f"https://example.com/p/{uuid.uuid4()}",
            extracted_json={},
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        snapshot_id = snapshot.id
    finally:
        session.close()

    client = TestClient(app)
    headers = {"X-Debug-Token": "secret"}

    prompt_resp = client.get(f"/v1/debug/prompts/{prompt_id}", headers=headers)
    assert prompt_resp.status_code == 200

    tool_resp = client.get(f"/v1/debug/tool-runs/{tool_run_id}", headers=headers)
    assert tool_resp.status_code == 200

    llm_resp = client.get(f"/v1/debug/llm-runs/{llm_run_id}", headers=headers)
    assert llm_resp.status_code == 200

    snapshot_resp = client.get(f"/v1/debug/snapshots/{snapshot_id}", headers=headers)
    assert snapshot_resp.status_code == 200


@pytest.mark.integration
def test_debug_guard_allows_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    compare_resp = client.post("/v1/discovery/compare")
    assert compare_resp.status_code == 200
    run_id = compare_resp.json()["run_id"]

    debug_resp = client.get(
        f"/v1/debug/compare-runs/{run_id}",
        headers={"X-Debug-Token": "secret"},
    )
    assert debug_resp.status_code == 200
