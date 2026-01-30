import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    jsonld = "jsonld"
    dom = "dom"
    minimal = "minimal"


class SnapshotStatus(str, Enum):
    ok = "ok"
    partial = "partial"
    indeterminate = "indeterminate"
    error = "error"


class SnapshotContext(BaseModel):
    run_id: uuid.UUID | None = None
    trace_id: str | None = None

    model_config = {"extra": "forbid"}


class SnapshotProviderConfig(BaseModel):
    provider_name: str
    timeout_seconds: int = 30
    user_agent: str | None = None
    flags: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class PageSnapshotResult(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    url: str
    final_url: str
    provider: str
    captured_at: datetime
    http_status: int | None = None
    extraction_method: ExtractionMethod
    status: SnapshotStatus
    extracted_json: dict = Field(default_factory=dict)
    digest_json: dict = Field(default_factory=dict)
    content_ref: str | None = None
    content_sha256: str | None = None
    content_size_bytes: int | None = None
    content_type: str | None = None
    rules_version: str | None = None
    missing_critical_json: dict | None = None
    digest_hash: str | None = None
    errors_json: dict | None = None

    model_config = {"extra": "forbid"}
