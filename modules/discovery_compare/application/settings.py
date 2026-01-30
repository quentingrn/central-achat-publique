from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscoveryCompareSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    mistral_api_key: str | None = Field(default=None, alias="MISTRAL_API_KEY")
    mistral_model: str = Field(default="mistral-large-latest", alias="MISTRAL_MODEL")
    llm_enabled: bool = Field(default=False, alias="DISCOVERY_COMPARE_LLM_ENABLED")
    agent_version_mode: str = Field(default="auto", alias="DISCOVERY_COMPARE_AGENT_VERSION_MODE")
    llm_timeout_seconds: int = Field(default=30, alias="DISCOVERY_COMPARE_LLM_TIMEOUT_SECONDS")

    snapshot_provider: str = Field(
        default="playwright",
        alias="DISCOVERY_COMPARE_SNAPSHOT_PROVIDER",
    )
    snapshot_require: bool = Field(
        default=False,
        alias="DISCOVERY_COMPARE_SNAPSHOT_REQUIRE",
    )
    playwright_mcp_mode: str = Field(default="http", alias="PLAYWRIGHT_MCP_MODE")
    playwright_mcp_command: str = Field(default="npx", alias="PLAYWRIGHT_MCP_COMMAND")
    playwright_mcp_args: str = Field(default="@playwright/mcp@latest", alias="PLAYWRIGHT_MCP_ARGS")
    playwright_mcp_cwd: str | None = Field(default=None, alias="PLAYWRIGHT_MCP_CWD")
    playwright_mcp_url: str | None = Field(default=None, alias="PLAYWRIGHT_MCP_URL")
    playwright_mcp_timeout_seconds: int = Field(default=30, alias="PLAYWRIGHT_MCP_TIMEOUT_SECONDS")
    playwright_mcp_install: bool = Field(default=False, alias="PLAYWRIGHT_MCP_INSTALL")
    snapshot_screenshot_enabled: bool = Field(
        default=False, alias="DISCOVERY_COMPARE_SNAPSHOT_SCREENSHOT_ENABLED"
    )
    snapshot_max_bytes: int | None = Field(
        default=1_000_000, alias="DISCOVERY_COMPARE_SNAPSHOT_MAX_BYTES"
    )
    snapshot_user_agent: str | None = Field(
        default=None, alias="DISCOVERY_COMPARE_SNAPSHOT_USER_AGENT"
    )

    product_candidate_provider: str = Field(
        default="stub", alias="DISCOVERY_COMPARE_PRODUCT_CANDIDATE_PROVIDER"
    )
    exa_mcp_url: str | None = Field(default=None, alias="EXA_MCP_URL")
    exa_mcp_timeout_seconds: int = Field(default=20, alias="EXA_MCP_TIMEOUT_SECONDS")
    exa_mcp_limit: int = Field(default=8, alias="EXA_MCP_LIMIT")
    exa_api_key: str | None = Field(default=None, alias="EXA_API_KEY")


def get_discovery_compare_settings() -> DiscoveryCompareSettings:
    return DiscoveryCompareSettings()
