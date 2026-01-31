from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from modules.discovery_compare.adapters.schemas.debug_run_v1 import (
    RunErrorTopV1,
    RunPhaseCountsV1,
)


class DiffSeverityV1(str, Enum):
    same = "same"
    changed = "changed"
    added = "added"
    removed = "removed"


class RunRefSetDiffV1(BaseModel):
    added_ids: list[str] = Field(default_factory=list)
    removed_ids: list[str] = Field(default_factory=list)
    common_count: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class RunPhaseDiffItemV1(BaseModel):
    phase_name: str
    left_status: str | None = None
    right_status: str | None = None
    severity: DiffSeverityV1
    left_message: str | None = None
    right_message: str | None = None

    model_config = {"extra": "forbid"}


class RunCountsDiffV1(BaseModel):
    left: RunPhaseCountsV1
    right: RunPhaseCountsV1
    severity: DiffSeverityV1

    model_config = {"extra": "forbid"}


class RunErrorTopDiffV1(BaseModel):
    left: RunErrorTopV1 | None = None
    right: RunErrorTopV1 | None = None
    severity: DiffSeverityV1

    model_config = {"extra": "forbid"}


class RunFieldDiffV1(BaseModel):
    left: str | None = None
    right: str | None = None
    severity: DiffSeverityV1

    model_config = {"extra": "forbid"}


class CompareRunDiffResponseV1(BaseModel):
    left_run_id: str
    right_run_id: str
    left_created_at: datetime | None = None
    right_created_at: datetime | None = None
    status_diff: RunFieldDiffV1
    source_url_diff: RunFieldDiffV1
    agent_version_diff: RunFieldDiffV1
    phase_counts: RunCountsDiffV1
    error_top: RunErrorTopDiffV1
    timeline: list[RunPhaseDiffItemV1]
    refs: dict[str, RunRefSetDiffV1]
    notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
