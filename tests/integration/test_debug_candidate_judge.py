import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from modules.discovery_compare.infrastructure.persistence.models import PageSnapshot
from shared.db.session import get_session
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


def test_debug_candidate_judge_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=False, token=None)
    client = TestClient(app)
    response = client.post(
        "/v1/debug/judge/candidates",
        json={
            "source": {"snapshot_id": "00000000-0000-0000-0000-000000000001"},
            "candidates": [{"snapshot_id": "00000000-0000-0000-0000-000000000002"}],
        },
    )
    assert response.status_code == 404


def test_debug_candidate_judge_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_debug_env(monkeypatch, enabled=True, token="secret")
    client = TestClient(app)
    response = client.post(
        "/v1/debug/judge/candidates",
        json={
            "source": {"snapshot_id": "00000000-0000-0000-0000-000000000001"},
            "candidates": [{"snapshot_id": "00000000-0000-0000-0000-000000000002"}],
        },
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_debug_candidate_judge_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    _set_debug_env(monkeypatch, enabled=True, token="secret")
    _set_stub_providers(monkeypatch)

    client = TestClient(app)
    response = client.post("/v1/discovery/compare")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    session = get_session()
    try:
        run_uuid = uuid.UUID(run_id)
        snapshots = (
            session.query(PageSnapshot)
            .filter(PageSnapshot.run_id == run_uuid)
            .order_by(PageSnapshot.created_at.asc())
            .all()
        )
        if len(snapshots) < 2:
            pytest.skip("Not enough snapshots created")
        source_id = snapshots[0].id
        candidate_ids = [snapshots[1].id]
        if len(snapshots) > 2:
            candidate_ids.append(snapshots[2].id)
    finally:
        session.close()

    payload = {
        "source": {"snapshot_id": str(source_id)},
        "candidates": [{"snapshot_id": str(cid)} for cid in candidate_ids],
        "ranking_top_k": 2,
    }
    judge_resp = client.post(
        "/v1/debug/judge/candidates",
        json=payload,
        headers={"X-Debug-Token": "secret"},
    )
    assert judge_resp.status_code == 200
    data = judge_resp.json()
    assert len(data["results"]) == len(candidate_ids)
    assert isinstance(data["ranked_top_k"], list)
    for result in data["results"]:
        assert result["verdict"] in {"yes", "no", "indeterminate"}
        assert "hard_filters" in result
        assert isinstance(result["breakdown"], dict)
