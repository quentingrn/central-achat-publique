import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RunPhaseCountsV1(BaseModel):
    ok: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class RunErrorTopV1(BaseModel):
    phase_name: str
    status: str
    message: str

    model_config = {"extra": "forbid"}


class CompareRunListItemV1(BaseModel):
    run_id: uuid.UUID
    created_at: datetime
    status: str
    source_url: str | None = None
    agent_version: str | None = None
    duration_ms: int | None = None
    phase_counts: RunPhaseCountsV1
    error_top: RunErrorTopV1 | None = None

    model_config = {"extra": "forbid"}


class CompareRunListResponseV1(BaseModel):
    items: list[CompareRunListItemV1]
    next_cursor: str | None = None

    model_config = {"extra": "forbid"}


class RunTimelineItemV1(BaseModel):
    phase_name: str
    status: str
    created_at: datetime
    message: str | None = None

    model_config = {"extra": "forbid"}


class RunRefsV1(BaseModel):
    snapshot_ids: list[uuid.UUID] = Field(default_factory=list)
    tool_run_ids: list[uuid.UUID] = Field(default_factory=list)
    llm_run_ids: list[uuid.UUID] = Field(default_factory=list)
    prompt_ids: list[uuid.UUID] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class CompareRunSummaryResponseV1(BaseModel):
    item: CompareRunListItemV1
    timeline: list[RunTimelineItemV1]
    refs: RunRefsV1

    model_config = {"extra": "forbid"}
