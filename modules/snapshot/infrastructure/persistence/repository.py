from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, column, insert, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from modules.snapshot.adapters.schemas import PageSnapshotResult
from modules.snapshot.application.ports import SnapshotRepository


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

    def append_snapshot(self, snapshot: PageSnapshotResult) -> uuid.UUID:
        values = {
            "id": snapshot.id,
            "run_id": self.run_id,
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
