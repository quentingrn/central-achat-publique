from __future__ import annotations

import httpx

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.ports import CapturedPage, SnapshotProvider


class HttpSnapshotProvider(SnapshotProvider):
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(follow_redirects=True)

    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        headers = {}
        if config.user_agent:
            headers["User-Agent"] = config.user_agent
        response = self._client.get(url, timeout=config.timeout_seconds, headers=headers)
        content_type = response.headers.get("content-type")
        metadata = {
            "headers": {
                "content-type": content_type,
                "server": response.headers.get("server"),
            }
        }
        return CapturedPage(
            requested_url=url,
            final_url=str(response.url),
            http_status=response.status_code,
            content_bytes=response.content,
            content_type=content_type,
            metadata=metadata,
        )
