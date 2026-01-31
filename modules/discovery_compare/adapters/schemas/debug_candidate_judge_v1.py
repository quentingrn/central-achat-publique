from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ProductDigestInputV1(BaseModel):
    snapshot_id: str | None = None
    url: str | None = None
    digest_v1: dict | None = None
    extraction_v1: dict | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _ensure_input_present(self):  # type: ignore[no-untyped-def]
        if not self.snapshot_id and not self.digest_v1 and not self.extraction_v1:
            raise ValueError("snapshot_id or digest_v1 or extraction_v1 required")
        return self

    model_config = {"extra": "forbid"}


class CandidateJudgeRequestV1(BaseModel):
    source: ProductDigestInputV1
    candidates: list[ProductDigestInputV1] = Field(min_length=1, max_length=20)
    ranking_top_k: int = Field(default=5, ge=1, le=10)
    mode: str | None = None
    notes: str | None = None

    model_config = {"extra": "forbid"}


class HardFilterResultV1(BaseModel):
    passed: bool
    reason_code: str
    details: dict | None = None

    model_config = {"extra": "forbid"}


class JudgeVerdictV1(str, Enum):
    yes = "yes"
    no = "no"
    indeterminate = "indeterminate"


class CandidateJudgeResultV1(BaseModel):
    candidate_index: int
    candidate_snapshot_id: str | None = None
    candidate_url: str | None = None
    verdict: JudgeVerdictV1
    comparability_score: float | None = None
    coverage_score: float | None = None
    identity_strength: float | None = None
    final_score: float | None = None
    hard_filters: list[HardFilterResultV1] = Field(default_factory=list)
    reasons_short: list[str] = Field(default_factory=list)
    signals_used: list[str] = Field(default_factory=list)
    missing_critical: list[str] = Field(default_factory=list)
    breakdown: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class CandidateJudgeResponseV1(BaseModel):
    request: CandidateJudgeRequestV1
    source_snapshot_id: str | None = None
    results: list[CandidateJudgeResultV1]
    ranked_top_k: list[int] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    raw: dict | None = None

    model_config = {"extra": "forbid"}
