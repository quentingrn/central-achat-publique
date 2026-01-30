from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from modules.snapshot.adapters.schemas import (
    PageSnapshotResult,
    SnapshotContext,
    SnapshotProviderConfig,
)


@dataclass(frozen=True)
class CapturedPage:
    requested_url: str
    final_url: str
    http_status: int | None
    content_bytes: bytes | None
    content_type: str | None
    metadata: dict


@dataclass(frozen=True)
class StoredArtifact:
    content_ref: str | None
    sha256: str | None
    size_bytes: int | None
    content_type: str | None


class SnapshotProvider(Protocol):
    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        raise NotImplementedError


class SnapshotRepository(Protocol):
    def append_snapshot(self, snapshot: PageSnapshotResult) -> uuid.UUID:
        raise NotImplementedError


class SnapshotArtifactStore(Protocol):
    def put(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
        raise NotImplementedError
