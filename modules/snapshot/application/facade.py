from __future__ import annotations

from datetime import UTC, datetime

from modules.snapshot.adapters.schemas import (
    PageSnapshotResult,
    SnapshotContext,
    SnapshotProviderConfig,
)
from modules.snapshot.application.ports import (
    SnapshotArtifactStore,
    SnapshotProvider,
    SnapshotRepository,
)
from modules.snapshot.domain.extraction import extract_minimal


def capture_page(
    url: str,
    context: SnapshotContext,
    provider_config: SnapshotProviderConfig,
    provider: SnapshotProvider,
    repository: SnapshotRepository,
    artifact_store: SnapshotArtifactStore,
) -> PageSnapshotResult:
    captured = provider.capture(url, context, provider_config)
    extraction = extract_minimal(url, captured.final_url, captured.content_bytes)

    content_ref = None
    content_size_bytes = None
    content_type = captured.content_type
    if captured.content_bytes:
        artifact = artifact_store.put(captured.content_bytes, captured.content_type)
        content_ref = artifact.content_ref
        content_size_bytes = artifact.size_bytes

    snapshot = PageSnapshotResult(
        url=url,
        final_url=captured.final_url,
        provider=provider_config.provider_name,
        captured_at=datetime.now(UTC),
        http_status=captured.http_status,
        extraction_method=extraction.method,
        status=extraction.status,
        extracted_json=extraction.extracted_json,
        digest_json=extraction.digest_json,
        content_ref=content_ref,
        content_size_bytes=content_size_bytes,
        content_type=content_type,
        errors_json=extraction.errors_json,
    )
    snapshot_id = repository.append_snapshot(snapshot)
    if snapshot_id != snapshot.id:
        snapshot = snapshot.model_copy(update={"id": snapshot_id})
    return snapshot
