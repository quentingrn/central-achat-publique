import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from modules.discovery_compare.infrastructure.mcp_clients.exa import ExaSearchResponse
from modules.discovery_compare.infrastructure.mcp_clients.playwright import (
    PlaywrightCaptureResponse,
)
from modules.discovery_compare.infrastructure.persistence.models import (
    CompareRun,
    LlmRun,
    PageSnapshot,
    ToolRun,
)
from shared.db.session import get_session
from tests.integration.db_utils import db_available


@pytest.mark.integration
def test_full_run_creates_nine_events(monkeypatch: pytest.MonkeyPatch) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Product","brand":{"@type":"Brand","name":"ACME"},"model":"X1"}
        </script>
      </head>
      <body>fixture</body>
    </html>
    """.strip()

    def fake_capture(self, request):  # type: ignore[no-untyped-def]
        return PlaywrightCaptureResponse(
            url_final=request.url,
            status_code=200,
            html=html,
            metadata={"mock": True},
            screenshot_base64=None,
            user_agent=request.user_agent,
        )

    monkeypatch.setenv("DISCOVERY_COMPARE_SNAPSHOT_PROVIDER", "playwright")
    monkeypatch.setenv("DISCOVERY_COMPARE_PRODUCT_CANDIDATE_PROVIDER", "exa")
    monkeypatch.setenv("PLAYWRIGHT_MCP_URL", "http://mock-playwright")
    monkeypatch.setenv("EXA_MCP_URL", "http://mock-exa")
    monkeypatch.setenv("EXA_API_KEY", "fake-key")
    monkeypatch.setattr(
        "modules.discovery_compare.infrastructure.mcp_clients.playwright.HttpPlaywrightMcpClient.capture",
        fake_capture,
    )

    def fake_search(self, request):  # type: ignore[no-untyped-def]
        return ExaSearchResponse(
            results=[
                {
                    "url": "https://example.com/p1",
                    "title": "ACME X1 Pro",
                    "snippet": "candidate 1",
                    "score": 0.91,
                },
                {
                    "url": "https://example.com/p2",
                    "title": "ACME X1 Plus",
                    "snippet": "candidate 2",
                    "score": 0.88,
                },
            ],
            metadata={"mock": True},
        )

    monkeypatch.setattr(
        "modules.discovery_compare.infrastructure.mcp_clients.exa.HttpExaMcpClient.search",
        fake_search,
    )

    client = TestClient(app)
    response = client.post("/v1/discovery/compare")
    assert response.status_code == 200
    payload = response.json()
    run_id = payload["run_id"]
    assert len(payload["diagnostics"]["phases"]) == 9
    fairness = payload["diagnostics"]["fairness"]
    assert fairness["comparability_score"] is not None
    assert fairness["coverage_score"] is not None
    assert fairness["diversity_score"] is not None
    assert payload["diagnostics"]["agent_version"]

    debug_response = client.get(f"/v1/debug/compare-runs/{run_id}")
    assert debug_response.status_code == 200
    debug_payload = debug_response.json()
    assert len(debug_payload["events"]) == 9
    comparability_events = [
        event for event in debug_payload["events"] if event["phase_name"] == "comparability_gate"
    ]
    assert comparability_events
    assert "excluded=" in (comparability_events[0]["message"] or "")

    session = get_session()
    try:
        run_uuid = uuid.UUID(run_id)
        run_row = session.query(CompareRun).filter(CompareRun.id == run_uuid).one()
        assert run_row.agent_version

        snapshots = session.query(PageSnapshot).all()
        assert len(snapshots) >= 2
        assert any("digest" in (snapshot.extracted_json or {}) for snapshot in snapshots)

        tool_runs = session.query(ToolRun).filter(ToolRun.run_id == run_uuid).all()
        assert tool_runs
        exa_runs = [tool for tool in tool_runs if tool.tool_name == "exa_mcp_recall"]
        assert exa_runs
        assert exa_runs[0].input_json["auth"]["exa_api_key"] == "fake-key"
        snapshot_tools = [tool for tool in tool_runs if "snapshot" in tool.tool_name]
        assert snapshot_tools
        for tool in snapshot_tools:
            assert tool.input_json
            assert tool.output_json

        llm_run = (
            session.query(LlmRun)
            .filter(LlmRun.run_id == run_uuid)
            .order_by(LlmRun.created_at.desc())
            .first()
        )
        assert llm_run is not None
        assert llm_run.prompt_content
        assert llm_run.json_schema
        assert llm_run.output_json is not None
        assert llm_run.output_validated_json is not None
        assert llm_run.validation_errors in (None, [])
        assert llm_run.model_params is not None
    finally:
        session.close()
