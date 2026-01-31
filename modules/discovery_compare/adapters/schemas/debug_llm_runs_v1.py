from datetime import datetime

from pydantic import BaseModel, Field


class LlmRunListItemV1(BaseModel):
    id: str
    run_id: str
    created_at: datetime | None = None
    status: str | None = None
    model_name: str | None = None
    prompt_id: str | None = None
    prompt_hash: str | None = None
    json_schema_hash: str | None = None
    phase_name: str | None = None
    has_validation_errors: bool
    validation_errors_count: int = Field(default=0, ge=0)
    short_error: str | None = None

    model_config = {"extra": "forbid"}


class LlmRunListResponseV1(BaseModel):
    run_id: str
    items: list[LlmRunListItemV1]
    counts: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class LlmRunDetailResponseV1(BaseModel):
    id: str
    run_id: str
    created_at: datetime | None = None
    status: str | None = None
    model_name: str | None = None
    model_params: dict | None = None
    phase_name: str | None = None
    prompt: dict
    json_schema: dict
    input_json: dict | None = None
    output_json: dict | None = None
    output_validated_json: dict | None = None
    validation_errors: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
