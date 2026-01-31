from __future__ import annotations

from modules.snapshot.adapters.schemas import SnapshotProviderConfig
from modules.snapshot.application.ports import SnapshotProvider
from modules.snapshot.application.settings import (
    SnapshotProviderSettings,
    get_snapshot_provider_settings,
)
from modules.snapshot.infrastructure.providers.browserbase_provider import (
    BrowserbaseSnapshotProvider,
)
from modules.snapshot.infrastructure.providers.http_provider import HttpSnapshotProvider
from modules.snapshot.infrastructure.providers.playwright_mcp_provider import (
    PlaywrightMcpSnapshotProvider,
)


def build_snapshot_provider(
    config: SnapshotProviderConfig,
    settings: SnapshotProviderSettings | None = None,
) -> SnapshotProvider:
    provider_name = config.provider_name.lower()
    settings = settings or get_snapshot_provider_settings()
    if provider_name == "http":
        return HttpSnapshotProvider()
    if provider_name == "playwright_mcp":
        return PlaywrightMcpSnapshotProvider(settings=settings)
    if provider_name == "browserbase":
        return BrowserbaseSnapshotProvider(settings=settings)
    raise ValueError(f"unsupported snapshot provider: {config.provider_name}")
