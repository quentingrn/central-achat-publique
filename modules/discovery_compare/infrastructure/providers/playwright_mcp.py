from __future__ import annotations

import base64
import binascii
import hashlib
import shlex
from dataclasses import dataclass

from modules.discovery_compare.application.ports import SnapshotProvider, SnapshotResult
from modules.discovery_compare.application.settings import DiscoveryCompareSettings
from modules.discovery_compare.domain.snapshot_extraction import build_snapshot_extraction
from modules.discovery_compare.infrastructure.mcp_clients.playwright import (
    HttpPlaywrightMcpClient,
    PlaywrightCaptureRequest,
    PlaywrightMcpClient,
    PlaywrightMcpError,
    PlaywrightMcpRegistry,
)


class SnapshotCaptureError(RuntimeError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class SnapshotArtifacts:
    html_hash: str | None
    html_bytes: int | None
    html_truncated: bool
    screenshot_hash: str | None
    screenshot_bytes: int | None


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _truncate_html(html: str | None, max_bytes: int | None) -> tuple[str | None, bool]:
    if html is None:
        return None, False
    raw = html.encode("utf-8")
    if max_bytes is None or len(raw) <= max_bytes:
        return html, False
    truncated = raw[:max_bytes]
    return truncated.decode("utf-8", errors="ignore"), True


def _artifact_from_payload(
    html: str | None, screenshot_base64: str | None, html_truncated: bool
) -> SnapshotArtifacts:
    html_hash = _hash_bytes(html.encode("utf-8")) if html else None
    screenshot_bytes = None
    screenshot_hash = None
    if screenshot_base64:
        try:
            screenshot_raw = base64.b64decode(screenshot_base64.encode("utf-8"))
        except binascii.Error:
            screenshot_raw = b""
        if screenshot_raw:
            screenshot_bytes = len(screenshot_raw)
            screenshot_hash = _hash_bytes(screenshot_raw)
    return SnapshotArtifacts(
        html_hash=html_hash,
        html_bytes=len(html.encode("utf-8")) if html else None,
        html_truncated=html_truncated,
        screenshot_hash=screenshot_hash,
        screenshot_bytes=screenshot_bytes,
    )


class PlaywrightMcpSnapshotProvider(SnapshotProvider):
    def __init__(
        self,
        settings: DiscoveryCompareSettings,
        client: PlaywrightMcpClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or self._build_client()

    def _build_client(self) -> PlaywrightMcpClient:
        if self.settings.playwright_mcp_mode == "stdio":
            command = [self.settings.playwright_mcp_command]
            command.extend(shlex.split(self.settings.playwright_mcp_args))
            return PlaywrightMcpRegistry.get_stdio_client(
                command=command,
                cwd=self.settings.playwright_mcp_cwd,
                timeout_seconds=self.settings.playwright_mcp_timeout_seconds,
            )
        if not self.settings.playwright_mcp_url:
            raise SnapshotCaptureError("PLAYWRIGHT_MCP_URL is not configured")
        return HttpPlaywrightMcpClient(self.settings.playwright_mcp_url)

    def capture(self, url: str) -> SnapshotResult:
        request = PlaywrightCaptureRequest(
            url=url,
            timeout_seconds=self.settings.playwright_mcp_timeout_seconds,
            screenshot=self.settings.snapshot_screenshot_enabled,
            max_bytes=self.settings.snapshot_max_bytes,
            user_agent=self.settings.snapshot_user_agent,
        )
        try:
            response = self.client.capture(request)
        except PlaywrightMcpError as exc:
            raise SnapshotCaptureError("playwright_mcp_error", {"error": str(exc)}) from exc

        status_code = response.status_code
        if status_code is not None and int(status_code) >= 400:
            raise SnapshotCaptureError(
                "playwright_mcp_http_error",
                {"status_code": status_code, "url_final": response.url_final},
            )

        html, html_truncated = _truncate_html(response.html, self.settings.snapshot_max_bytes)
        if not html:
            raise SnapshotCaptureError(
                "playwright_mcp_empty_html",
                {"status_code": status_code, "url_final": response.url_final},
            )

        extracted, digest = build_snapshot_extraction(html)
        artifacts = _artifact_from_payload(html, response.screenshot_base64, html_truncated)
        metadata = {
            "requested_url": url,
            "url_final": response.url_final,
            "status_code": status_code,
            "user_agent": response.user_agent,
            "html_hash": artifacts.html_hash,
            "html_bytes": artifacts.html_bytes,
            "html_truncated": artifacts.html_truncated,
            "screenshot_hash": artifacts.screenshot_hash,
            "screenshot_bytes": artifacts.screenshot_bytes,
        }
        metadata.update(response.metadata or {})

        return SnapshotResult(
            requested_url=url,
            url_final=response.url_final or url,
            status_code=status_code,
            html=html,
            metadata=metadata,
            extracted_json=extracted,
            digest_json=digest,
            screenshot_base64=response.screenshot_base64,
        )
