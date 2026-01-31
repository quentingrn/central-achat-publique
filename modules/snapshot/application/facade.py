from __future__ import annotations

import hashlib
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
from modules.snapshot.domain.extraction import extract_structured_v1
from modules.snapshot.infrastructure.providers.factory import build_snapshot_provider


def capture_page(
    url: str,
    context: SnapshotContext,
    provider_config: SnapshotProviderConfig,
    provider: SnapshotProvider | None,
    repository: SnapshotRepository,
    artifact_store: SnapshotArtifactStore,
) -> PageSnapshotResult:
    if context.run_id is not None:
        existing = repository.find_by_run_id_url(context.run_id, url)
        if existing is not None:
            return existing

    provider_instance = provider or build_snapshot_provider(provider_config)
    captured = provider_instance.capture(url, context, provider_config)
    content_ref = None
    content_sha256 = None
    content_size_bytes = None
    content_type = captured.content_type or "text/html; charset=utf-8"
    extraction = extract_structured_v1(
        url=url,
        final_url=captured.final_url,
        content_bytes=captured.content_bytes,
        content_type=content_type,
    )
    errors_json = extraction.errors_json
    proof_mode = str(provider_config.flags.get("proof_mode", "off") or "off").lower()
    if captured.content_bytes:
        content_sha256 = hashlib.sha256(captured.content_bytes).hexdigest()
        content_size_bytes = len(captured.content_bytes)
        if proof_mode in {"debug", "audit"}:
            artifact = artifact_store.put_bytes(captured.content_bytes, content_type)
            content_ref = artifact.content_ref
            content_sha256 = artifact.sha256 or content_sha256
            content_size_bytes = artifact.size_bytes or content_size_bytes
            content_type = artifact.content_type or content_type
    else:
        if errors_json is None:
            errors_json = {"reason": "no_content_captured"}

    extracted_json = dict(extraction.extracted_json)
    extracted_json["digest"] = extraction.digest_json

    snapshot = PageSnapshotResult(
        url=url,
        final_url=captured.final_url,
        provider=provider_config.provider_name,
        captured_at=datetime.now(UTC),
        http_status=captured.http_status,
        extraction_method=extraction.method,
        status=extraction.status,
        extracted_json=extracted_json,
        digest_json=extraction.digest_json,
        digest_hash=extraction.digest_hash,
        content_ref=content_ref,
        content_sha256=content_sha256,
        content_size_bytes=content_size_bytes,
        content_type=content_type,
        errors_json=errors_json,
        missing_critical_json=extraction.missing_critical_json,
    )
    snapshot_id = repository.append_snapshot(snapshot, context.run_id)
    if snapshot_id != snapshot.id:
        snapshot = snapshot.model_copy(update={"id": snapshot_id})
    return snapshot
