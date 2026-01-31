from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, column, insert, select, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from modules.snapshot.adapters.schemas import (
    ExtractionMethod,
    PageSnapshotResult,
    SnapshotStatus,
)
from modules.snapshot.application.ports import (
    SnapshotArtifactStore,
    SnapshotRepository,
    StoredArtifact,
)


class SqlSnapshotRepository(SnapshotRepository):
    def __init__(
        self, session: Session, default_product_id: uuid.UUID, run_id: uuid.UUID | None = None
    ) -> None:
        self.session = session
        self.default_product_id = default_product_id
        self.run_id = run_id
        self._table = table(
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
        )

    def append_snapshot(self, snapshot: PageSnapshotResult, run_id: uuid.UUID | None) -> uuid.UUID:
        run_id_value = run_id if run_id is not None else self.run_id
        values = {
            "id": snapshot.id,
            "run_id": run_id_value,
            "product_id": self.default_product_id,
            "url": snapshot.url,
            "final_url": snapshot.final_url,
            "provider": snapshot.provider,
            "http_status": snapshot.http_status,
            "captured_at": snapshot.captured_at,
            "extraction_method": snapshot.extraction_method.value,
            "extraction_status": snapshot.status.value,
            "rules_version": snapshot.rules_version,
            "content_ref": snapshot.content_ref,
            "content_sha256": snapshot.content_sha256,
            "content_size_bytes": snapshot.content_size_bytes,
            "content_type": snapshot.content_type,
            "errors_json": snapshot.errors_json,
            "missing_critical_json": snapshot.missing_critical_json,
            "digest_hash": snapshot.digest_hash,
            "extracted_json": snapshot.extracted_json,
        }
        self.session.execute(insert(self._table).values(**values))
        self.session.commit()
        return snapshot.id

    def find_by_run_id_url(self, run_id: uuid.UUID, url: str) -> PageSnapshotResult | None:
        stmt = (
            select(self._table)
            .where(self._table.c.run_id == run_id, self._table.c.url == url)
            .limit(1)
        )
        row = self.session.execute(stmt).mappings().first()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    @staticmethod
    def _row_to_snapshot(row: dict) -> PageSnapshotResult:
        extracted = row.get("extracted_json") or {}
        digest = extracted.get("digest") or {}
        method_value = row.get("extraction_method") or ExtractionMethod.minimal.value
        status_value = row.get("extraction_status") or SnapshotStatus.indeterminate.value
        try:
            method = ExtractionMethod(method_value)
        except ValueError:
            method = ExtractionMethod.minimal
        try:
            status = SnapshotStatus(status_value)
        except ValueError:
            status = SnapshotStatus.indeterminate
        return PageSnapshotResult(
            id=row["id"],
            url=row["url"],
            final_url=row.get("final_url") or row["url"],
            provider=row.get("provider") or "unknown",
            captured_at=row["captured_at"],
            http_status=row.get("http_status"),
            extraction_method=method,
            status=status,
            extracted_json=extracted,
            digest_json=digest,
            digest_hash=row.get("digest_hash"),
            content_ref=row.get("content_ref"),
            content_sha256=row.get("content_sha256"),
            content_size_bytes=row.get("content_size_bytes"),
            content_type=row.get("content_type"),
            rules_version=row.get("rules_version"),
            errors_json=row.get("errors_json"),
            missing_critical_json=row.get("missing_critical_json"),
        )


class InMemoryArtifactStore(SnapshotArtifactStore):
    def __init__(self) -> None:
        self.items = []

    def put_bytes(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
        ref = f"mem://{uuid.uuid4()}"
        self.items.append((ref, content_bytes, content_type))
        return StoredArtifact(
            content_ref=ref,
            sha256=None,
            size_bytes=len(content_bytes),
            content_type=content_type,
        )
