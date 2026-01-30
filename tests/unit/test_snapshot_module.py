import uuid

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.facade import capture_page
from modules.snapshot.application.ports import StoredArtifact
from modules.snapshot.infrastructure.providers.stubs import StubSnapshotProvider


class InMemorySnapshotRepo:
    def __init__(self) -> None:
        self.snapshots = []

    def append_snapshot(self, snapshot):  # type: ignore[no-untyped-def]
        self.snapshots.append(snapshot)
        return snapshot.id


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self.items = []

    def put(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
        ref = f"mem://{uuid.uuid4()}"
        self.items.append((ref, content_bytes, content_type))
        return StoredArtifact(
            content_ref=ref,
            sha256=None,
            size_bytes=len(content_bytes),
            content_type=content_type,
        )


def test_capture_page_minimal_stub() -> None:
    provider = StubSnapshotProvider()
    repo = InMemorySnapshotRepo()
    store = InMemoryArtifactStore()
    result = capture_page(
        url="https://example.com",
        context=SnapshotContext(run_id=None),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    assert result.url == "https://example.com"
    assert result.final_url == "https://example.com"
    assert result.provider == "stub"
    assert result.extraction_method.value == "minimal"
    assert result.content_ref is not None
    assert repo.snapshots
