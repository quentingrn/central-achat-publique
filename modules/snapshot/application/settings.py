from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SnapshotProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    playwright_mcp_mode: str = Field(default="http", alias="PLAYWRIGHT_MCP_MODE")
    playwright_mcp_command: str = Field(default="npx", alias="PLAYWRIGHT_MCP_COMMAND")
    playwright_mcp_args: str = Field(default="@playwright/mcp@latest", alias="PLAYWRIGHT_MCP_ARGS")
    playwright_mcp_cwd: str | None = Field(default=None, alias="PLAYWRIGHT_MCP_CWD")
    playwright_mcp_url: str | None = Field(default=None, alias="PLAYWRIGHT_MCP_URL")
    playwright_mcp_timeout_seconds: int = Field(default=30, alias="PLAYWRIGHT_MCP_TIMEOUT_SECONDS")

    browserbase_api_key: str | None = Field(default=None, alias="BROWSERBASE_API_KEY")
    browserbase_project_id: str | None = Field(default=None, alias="BROWSERBASE_PROJECT_ID")
    browserbase_timeout_seconds: int = Field(default=30, alias="BROWSERBASE_TIMEOUT_SECONDS")


def get_snapshot_provider_settings() -> SnapshotProviderSettings:
    return SnapshotProviderSettings()
