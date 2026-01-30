import uuid
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PhaseNameV1(str, Enum):
    source_snapshot_capture = "source_snapshot_capture"
    product_candidates_recall = "product_candidates_recall"
    candidate_snapshot_capture = "candidate_snapshot_capture"
    comparability_gate = "comparability_gate"
    criteria_selection = "criteria_selection"
    product_comparison_build = "product_comparison_build"
    offers_recall_and_fetch = "offers_recall_and_fetch"
    offers_normalize_and_dedupe = "offers_normalize_and_dedupe"
    final_response_assemble = "final_response_assemble"


class ProductDigestV1(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    brand: str
    model: str
    source_url: str | None = None
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ComparableV1(BaseModel):
    product: ProductDigestV1
    comparability_score: float | None = None
    reasons_short: list[str] = Field(default_factory=list)
    signals_used: list[str] = Field(default_factory=list)
    missing_critical: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class OfferV1(BaseModel):
    offer_url: str
    seller: str | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class PhaseDiagnosticsV1(BaseModel):
    name: PhaseNameV1
    status: Literal["ok", "error", "skipped", "indeterminate"]
    duration_ms: int | None = None
    message: str | None = None

    model_config = {"extra": "forbid"}


class FairnessMetricsV1(BaseModel):
    comparability_score: float | None = None
    coverage_score: float | None = None
    diversity_score: float | None = None
    notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class RunDiagnosticsV1(BaseModel):
    phases: list[PhaseDiagnosticsV1]
    fairness: FairnessMetricsV1 | None = None
    agent_version: str | None = None

    model_config = {"extra": "forbid"}


class ComparabilityGateOutputV1(BaseModel):
    comparables: list[ComparableV1]

    model_config = {"extra": "forbid"}


class AgentRunOutputV1(BaseModel):
    run_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_product: ProductDigestV1
    comparables: list[ComparableV1] = Field(default_factory=list)
    offers: list[OfferV1] = Field(default_factory=list)
    diagnostics: RunDiagnosticsV1

    model_config = {"extra": "forbid"}
