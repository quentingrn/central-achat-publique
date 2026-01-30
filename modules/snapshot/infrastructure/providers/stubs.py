from __future__ import annotations

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.ports import CapturedPage, SnapshotProvider


class StubSnapshotProvider(SnapshotProvider):
    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        content = f"<html><body>{url}</body></html>".encode()
        return CapturedPage(
            requested_url=url,
            final_url=url,
            http_status=200,
            content_bytes=content,
            content_type="text/html",
            metadata={"stub": True},
        )
