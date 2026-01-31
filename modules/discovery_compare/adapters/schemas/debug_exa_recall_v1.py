from datetime import datetime

from pydantic import BaseModel, Field


class ExaRecallRequestV1(BaseModel):
    query: str
    num_results: int = Field(default=10, ge=1, le=20)
    include_domains: list[str] | None = None
    exclude_domains: list[str] | None = None
    language: str | None = None
    country: str | None = None
    use_autoprompt: bool | None = None

    model_config = {"extra": "forbid"}


class ExaResultItemV1(BaseModel):
    rank: int
    title: str | None = None
    url: str
    domain: str | None = None
    score: float | None = None
    snippet: str | None = None
    published_at: datetime | None = None

    model_config = {"extra": "forbid"}


class ExaRecallResponseV1(BaseModel):
    request: ExaRecallRequestV1
    provider: str
    took_ms: int | None = None
    items: list[ExaResultItemV1]
    raw: dict | None = None
    errors: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
