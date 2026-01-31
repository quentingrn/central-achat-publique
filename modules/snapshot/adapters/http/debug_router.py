import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, String, column, desc, func, insert, select, table
from sqlalchemy.dialects import postgresql

from apps.api.guards import require_debug_access
from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.adapters.schemas.debug_snapshot_v1 import (
    SnapshotByUrlListResponseV1,
    SnapshotCaptureRequestV1,
    SnapshotCaptureResponseV1,
    SnapshotGetResponseV1,
    SnapshotLookupV1,
)
from modules.snapshot.application.facade import capture_page
from modules.snapshot.infrastructure.persistence.repository import (
    InMemoryArtifactStore,
    SqlSnapshotRepository,
)
from modules.snapshot.infrastructure.providers.stubs import StubSnapshotProvider
from shared.db.session import get_session

router = APIRouter(
    prefix="/v1/debug",
    tags=["debug"],
    dependencies=[Depends(require_debug_access)],
)

_PRODUCTS_TABLE = table(
    "products",
    column("id", postgresql.UUID(as_uuid=True)),
    column("brand", String),
    column("model", String),
    column("source_url", String),
)

_SNAPSHOTS_TABLE = table(
    "page_snapshots",
    column("id", postgresql.UUID(as_uuid=True)),
    column("run_id", postgresql.UUID(as_uuid=True)),
    column("product_id", postgresql.UUID(as_uuid=True)),
    column("url", String),
    column("final_url", String),
    column("provider", String),
    column("http_status", Integer),
    column("captured_at"),
    column("extraction_method", String),
    column("extraction_status", String),
    column("rules_version", String),
    column("content_ref", String),
    column("content_sha256", String),
    column("content_size_bytes", Integer),
    column("content_type", String),
    column("errors_json", postgresql.JSONB),
    column("missing_critical_json", postgresql.JSONB),
    column("digest_hash", String),
    column("extracted_json", postgresql.JSONB),
    column("created_at"),
)


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid snapshot_id") from exc


def _missing_list(raw: object | None) -> list[str]:
    if isinstance(raw, dict):
        value = raw.get("missing") or raw.get("missing_critical")
        if isinstance(value, list):
            return [str(item) for item in value]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _errors_list(raw: object | None) -> list[dict]:
    if isinstance(raw, dict):
        value = raw.get("errors")
        if isinstance(value, list):
            return value
        if raw:
            return [raw]
    if isinstance(raw, list):
        return raw
    return []


def _snapshot_lookup(row: dict) -> SnapshotLookupV1:
    missing = _missing_list(row.get("missing_critical_json"))
    errors = _errors_list(row.get("errors_json"))
    captured_at = row.get("captured_at") or row.get("created_at")
    return SnapshotLookupV1(
        snapshot_id=str(row.get("id")),
        run_id=str(row.get("run_id")) if row.get("run_id") else None,
        url=row.get("url") or "",
        final_url=row.get("final_url"),
        provider=row.get("provider") or "unknown",
        captured_at=captured_at,
        extraction_method=row.get("extraction_method"),
        extraction_status=row.get("extraction_status"),
        rules_version=row.get("rules_version"),
        digest_hash=row.get("digest_hash"),
        http_status=row.get("http_status"),
        content_sha256=row.get("content_sha256"),
        content_size_bytes=row.get("content_size_bytes"),
        content_type=row.get("content_type"),
        missing_critical=missing,
        errors=errors,
    )


def _snapshot_response(row: dict) -> SnapshotGetResponseV1:
    raw_extracted = row.get("extracted_json")
    extraction_v1 = None
    digest_v1 = None
    if isinstance(raw_extracted, dict):
        if raw_extracted.get("extraction_version") == "v1":
            extraction_v1 = raw_extracted
        digest_candidate = raw_extracted.get("digest")
        if isinstance(digest_candidate, dict):
            digest_v1 = digest_candidate
    return SnapshotGetResponseV1(
        item=_snapshot_lookup(row),
        extraction_v1=extraction_v1,
        digest_v1=digest_v1,
        raw_extracted_json=raw_extracted if isinstance(raw_extracted, dict) else None,
    )


def _create_debug_product_id(session) -> uuid.UUID:
    product_id = uuid.uuid4()
    session.execute(
        insert(_PRODUCTS_TABLE).values(
            id=product_id,
            brand="DEBUG",
            model="DEBUG",
            source_url=None,
        )
    )
    session.commit()
    return product_id


def _resolve_provider_name(provider: str | None) -> str:
    if not provider:
        return "http"
    normalized = provider.strip().lower()
    if normalized == "playwright":
        return "playwright_mcp"
    return normalized


def _build_provider_config(request: SnapshotCaptureRequestV1) -> SnapshotProviderConfig:
    flags: dict[str, str | int | float | bool | None] = {}
    if request.proof_mode is not None:
        proof = request.proof_mode.strip().lower()
        if proof in {"none", "off"}:
            proof = "off"
        flags["proof_mode"] = proof
    if request.screenshot_enabled is not None:
        flags["screenshot"] = request.screenshot_enabled
    if request.max_bytes is not None:
        flags["max_bytes"] = request.max_bytes
    return SnapshotProviderConfig(
        provider_name=_resolve_provider_name(request.provider),
        flags=flags,
    )


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotGetResponseV1)
def get_snapshot(snapshot_id: str) -> SnapshotGetResponseV1:
    session = get_session()
    try:
        snapshot_uuid = _parse_uuid(snapshot_id)
        row = (
            session.execute(select(_SNAPSHOTS_TABLE).where(_SNAPSHOTS_TABLE.c.id == snapshot_uuid))
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="snapshot not found")
        return _snapshot_response(row)
    finally:
        session.close()


@router.get("/snapshots:by-url", response_model=SnapshotByUrlListResponseV1)
def list_snapshots_by_url(
    url: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
) -> SnapshotByUrlListResponseV1:
    session = get_session()
    try:
        ordering = desc(
            func.coalesce(_SNAPSHOTS_TABLE.c.captured_at, _SNAPSHOTS_TABLE.c.created_at)
        )
        rows = (
            session.execute(
                select(_SNAPSHOTS_TABLE)
                .where(_SNAPSHOTS_TABLE.c.url == url)
                .order_by(ordering)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        items = [_snapshot_lookup(row) for row in rows]
        return SnapshotByUrlListResponseV1(items=items)
    finally:
        session.close()


@router.post("/snapshots:capture", response_model=SnapshotCaptureResponseV1)
def capture_snapshot(payload: SnapshotCaptureRequestV1) -> SnapshotCaptureResponseV1:
    session = get_session()
    try:
        product_id = _create_debug_product_id(session)
        provider_config = _build_provider_config(payload)
        provider = None
        if provider_config.provider_name == "stub":
            provider = StubSnapshotProvider()
        snapshot = capture_page(
            url=payload.url,
            context=SnapshotContext(run_id=None),
            provider_config=provider_config,
            provider=provider,
            repository=SqlSnapshotRepository(
                session=session,
                default_product_id=product_id,
                run_id=None,
            ),
            artifact_store=InMemoryArtifactStore(),
        )
        row = (
            session.execute(select(_SNAPSHOTS_TABLE).where(_SNAPSHOTS_TABLE.c.id == snapshot.id))
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=500, detail="snapshot not persisted")
        summary = _snapshot_response(row)
        return SnapshotCaptureResponseV1(
            snapshot_id=str(snapshot.id),
            url=snapshot.url,
            provider=snapshot.provider,
            status=snapshot.status.value,
            summary=summary,
        )
    finally:
        session.close()
