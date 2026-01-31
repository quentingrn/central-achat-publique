from __future__ import annotations

import hashlib
from pathlib import Path

from modules.snapshot.application.ports import SnapshotArtifactStore, StoredArtifact


class LocalArtifactStore(SnapshotArtifactStore):
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        path = self.base_path / sha256
        path.write_bytes(content_bytes)
        return StoredArtifact(
            content_ref=f"file:{sha256}",
            sha256=sha256,
            size_bytes=len(content_bytes),
            content_type=content_type,
        )
