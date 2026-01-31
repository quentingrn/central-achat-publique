from datetime import datetime

from pydantic import BaseModel, Field


class SnapshotLookupV1(BaseModel):
    snapshot_id: str
    run_id: str | None = None
    url: str
    final_url: str | None = None
    provider: str
    captured_at: datetime | None = None
    extraction_method: str | None = None
    extraction_status: str | None = None
    rules_version: str | None = None
    digest_hash: str | None = None
    http_status: int | None = None
    content_sha256: str | None = None
    content_size_bytes: int | None = None
    content_type: str | None = None
    missing_critical: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class SnapshotGetResponseV1(BaseModel):
    item: SnapshotLookupV1
    extraction_v1: dict | None = None
    digest_v1: dict | None = None
    raw_extracted_json: dict | None = None

    model_config = {"extra": "forbid"}


class SnapshotByUrlListResponseV1(BaseModel):
    items: list[SnapshotLookupV1]

    model_config = {"extra": "forbid"}


class SnapshotCaptureRequestV1(BaseModel):
    url: str
    provider: str | None = None
    proof_mode: str | None = None
    screenshot_enabled: bool | None = None
    max_bytes: int | None = None

    model_config = {"extra": "forbid"}


class SnapshotCaptureResponseV1(BaseModel):
    snapshot_id: str
    url: str
    provider: str
    status: str
    summary: SnapshotGetResponseV1

    model_config = {"extra": "forbid"}
