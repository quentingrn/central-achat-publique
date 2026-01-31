from fastapi import Depends, Header, HTTPException

from apps.api.settings import DebugApiSettings, get_debug_api_settings


def require_debug_access(
    x_debug_token: str | None = Header(default=None, alias="X-Debug-Token"),
    settings: DebugApiSettings = Depends(get_debug_api_settings),  # noqa: B008
) -> None:
    if not settings.debug_api_enabled:
        raise HTTPException(status_code=404, detail="not found")
    if not settings.debug_api_token or x_debug_token != settings.debug_api_token:
        raise HTTPException(status_code=403, detail="forbidden")
