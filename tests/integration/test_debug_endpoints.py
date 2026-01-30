import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from modules.discovery_compare.adapters.schemas import PhaseNameV1
from modules.discovery_compare.application.run_recorder import RunRecorder
from modules.discovery_compare.infrastructure.persistence.models import PageSnapshot, Product
from shared.db.session import get_session
from tests.integration.db_utils import db_available


@pytest.mark.integration
def test_debug_endpoints_run_and_event() -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    session = get_session()
    recorder = RunRecorder(session)
    try:
        run = recorder.create_run(source_url="https://example.com/p")
        recorder.add_event(run.id, PhaseNameV1.source_snapshot_capture.value, "ok")
        run_id = run.id
    finally:
        session.close()

    client = TestClient(app)
    response = client.get(f"/v1/debug/compare-runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["events"][0]["phase_name"] == PhaseNameV1.source_snapshot_capture.value


@pytest.mark.integration
def test_debug_endpoints_artifacts() -> None:
    if not db_available():
        pytest.skip("Postgres not available")

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

    prompt_resp = client.get(f"/v1/debug/prompts/{prompt_id}")
    assert prompt_resp.status_code == 200

    tool_resp = client.get(f"/v1/debug/tool-runs/{tool_run_id}")
    assert tool_resp.status_code == 200

    llm_resp = client.get(f"/v1/debug/llm-runs/{llm_run_id}")
    assert llm_resp.status_code == 200

    snapshot_resp = client.get(f"/v1/debug/snapshots/{snapshot_id}")
    assert snapshot_resp.status_code == 200
