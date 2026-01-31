from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DebugApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    debug_api_enabled: bool = Field(default=False, alias="DEBUG_API_ENABLED")
    debug_api_token: str = Field(default="", alias="DEBUG_API_TOKEN")


def get_debug_api_settings() -> DebugApiSettings:
    return DebugApiSettings()
