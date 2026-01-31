from __future__ import annotations

import shlex

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.ports import CapturedPage, SnapshotProvider
from modules.snapshot.application.settings import SnapshotProviderSettings
from modules.snapshot.infrastructure.mcp_clients.playwright import (
    HttpPlaywrightMcpClient,
    PlaywrightCaptureRequest,
    PlaywrightMcpClient,
    PlaywrightMcpError,
    PlaywrightMcpRegistry,
)


class PlaywrightMcpSnapshotProvider(SnapshotProvider):
    def __init__(
        self,
        settings: SnapshotProviderSettings,
        client: PlaywrightMcpClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    def _build_client(self) -> PlaywrightMcpClient | None:
        if self._settings.playwright_mcp_mode == "stdio":
            command = [self._settings.playwright_mcp_command]
            command.extend(shlex.split(self._settings.playwright_mcp_args))
            return PlaywrightMcpRegistry.get_stdio_client(
                command=command,
                cwd=self._settings.playwright_mcp_cwd,
                timeout_seconds=self._settings.playwright_mcp_timeout_seconds,
            )
        if not self._settings.playwright_mcp_url:
            return None
        return HttpPlaywrightMcpClient(self._settings.playwright_mcp_url)

    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        client = self._client or self._build_client()
        if client is None:
            return CapturedPage(
                requested_url=url,
                final_url=url,
                http_status=None,
                content_bytes=None,
                content_type=None,
                metadata={
                    "error": {
                        "code": "playwright_mcp_not_configured",
                        "message": "PLAYWRIGHT_MCP_URL is missing",
                    }
                },
            )
        request = PlaywrightCaptureRequest(
            url=url,
            timeout_seconds=config.timeout_seconds,
            user_agent=config.user_agent,
            screenshot=None,
            max_bytes=config.flags.get("max_bytes") if config.flags else None,
        )
        try:
            response = client.capture(request)
        except PlaywrightMcpError as exc:
            return CapturedPage(
                requested_url=url,
                final_url=url,
                http_status=None,
                content_bytes=None,
                content_type=None,
                metadata={"error": {"code": "playwright_mcp_error", "message": str(exc)}},
            )
        html_bytes = response.html.encode("utf-8") if response.html else None
        content_type = response.content_type or "text/html; charset=utf-8"
        return CapturedPage(
            requested_url=url,
            final_url=response.url_final or url,
            http_status=response.status_code,
            content_bytes=html_bytes,
            content_type=content_type,
            metadata=response.metadata,
        )
