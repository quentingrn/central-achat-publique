from __future__ import annotations

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.ports import CapturedPage, SnapshotProvider
from modules.snapshot.application.settings import SnapshotProviderSettings


class BrowserbaseSnapshotProvider(SnapshotProvider):
    def __init__(self, settings: SnapshotProviderSettings) -> None:
        self._settings = settings

    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        if not self._settings.browserbase_api_key or not self._settings.browserbase_project_id:
            return CapturedPage(
                requested_url=url,
                final_url=url,
                http_status=None,
                content_bytes=None,
                content_type=None,
                metadata={
                    "error": {
                        "code": "browserbase_not_configured",
                        "message": "BROWSERBASE_API_KEY or BROWSERBASE_PROJECT_ID missing",
                    }
                },
            )
        return CapturedPage(
            requested_url=url,
            final_url=url,
            http_status=None,
            content_bytes=None,
            content_type=None,
            metadata={
                "error": {
                    "code": "browserbase_not_implemented",
                    "message": "Browserbase adapter placeholder",
                }
            },
        )
