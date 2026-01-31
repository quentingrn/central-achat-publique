import httpx

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.settings import SnapshotProviderSettings
from modules.snapshot.infrastructure.mcp_clients.playwright import PlaywrightCaptureResponse
from modules.snapshot.infrastructure.providers.browserbase_provider import (
    BrowserbaseSnapshotProvider,
)
from modules.snapshot.infrastructure.providers.factory import build_snapshot_provider
from modules.snapshot.infrastructure.providers.http_provider import HttpSnapshotProvider
from modules.snapshot.infrastructure.providers.playwright_mcp_provider import (
    PlaywrightMcpSnapshotProvider,
)


def test_provider_factory_returns_expected_types() -> None:
    settings = SnapshotProviderSettings(
        playwright_mcp_mode="stdio",
        playwright_mcp_command="echo",
        playwright_mcp_args="{}",
        playwright_mcp_cwd=None,
        playwright_mcp_url=None,
    )
    assert isinstance(
        build_snapshot_provider(SnapshotProviderConfig(provider_name="http"), settings=settings),
        HttpSnapshotProvider,
    )
    assert isinstance(
        build_snapshot_provider(
            SnapshotProviderConfig(provider_name="playwright_mcp"), settings=settings
        ),
        PlaywrightMcpSnapshotProvider,
    )
    assert isinstance(
        build_snapshot_provider(
            SnapshotProviderConfig(provider_name="browserbase"), settings=settings
        ),
        BrowserbaseSnapshotProvider,
    )


def test_http_provider_capture_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<html>ok</html>",
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, follow_redirects=True)
    provider = HttpSnapshotProvider(client=client)
    result = provider.capture(
        url="https://example.com",
        context=SnapshotContext(run_id=None),
        config=SnapshotProviderConfig(provider_name="http"),
    )
    assert result.http_status == 200
    assert result.content_bytes
    assert result.content_type == "text/html; charset=utf-8"


def test_playwright_provider_uses_client_override() -> None:
    class DummyClient:
        def capture(self, request):  # type: ignore[no-untyped-def]
            return PlaywrightCaptureResponse(
                url_final=request.url,
                status_code=200,
                html="<html>ok</html>",
                metadata={"stub": True},
                content_type="text/html; charset=utf-8",
            )

    settings = SnapshotProviderSettings(playwright_mcp_mode="http", playwright_mcp_url="http://x")
    provider = PlaywrightMcpSnapshotProvider(settings=settings, client=DummyClient())
    result = provider.capture(
        url="https://example.com",
        context=SnapshotContext(run_id=None),
        config=SnapshotProviderConfig(provider_name="playwright_mcp"),
    )
    assert result.content_bytes
    assert result.metadata["stub"] is True


def test_browserbase_provider_missing_config_returns_error() -> None:
    settings = SnapshotProviderSettings(
        browserbase_api_key=None,
        browserbase_project_id=None,
    )
    provider = BrowserbaseSnapshotProvider(settings=settings)
    result = provider.capture(
        url="https://example.com",
        context=SnapshotContext(run_id=None),
        config=SnapshotProviderConfig(provider_name="browserbase"),
    )
    assert result.content_bytes is None
    assert result.metadata["error"]["code"] == "browserbase_not_configured"
