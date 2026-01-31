import uuid

from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.facade import capture_page
from modules.snapshot.application.ports import StoredArtifact
from modules.snapshot.infrastructure.providers.stubs import StubSnapshotProvider


class InMemorySnapshotRepo:
    def __init__(self) -> None:
        self.snapshots = []

    def append_snapshot(self, snapshot, run_id):  # type: ignore[no-untyped-def]
        self.snapshots.append((run_id, snapshot))
        return snapshot.id

    def find_by_run_id_url(self, run_id, url):  # type: ignore[no-untyped-def]
        for stored_run_id, snapshot in self.snapshots:
            if stored_run_id == run_id and snapshot.url == url:
                return snapshot
        return None


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self.items = []

    def put_bytes(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
        ref = f"mem://{uuid.uuid4()}"
        sha256 = __import__("hashlib").sha256(content_bytes).hexdigest()
        self.items.append((ref, content_bytes, content_type))
        return StoredArtifact(
            content_ref=ref,
            sha256=sha256,
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
    assert result.status.value == "indeterminate"
    assert result.extracted_json["extraction_version"] == "v1"
    assert "digest" in result.extracted_json
    assert result.content_ref is None
    assert result.content_sha256 is not None
    assert result.content_size_bytes is not None
    assert result.content_type == "text/html; charset=utf-8"
    assert repo.snapshots


def test_capture_page_sha256_stable() -> None:
    provider = StubSnapshotProvider()
    repo = InMemorySnapshotRepo()
    store = InMemoryArtifactStore()
    first = capture_page(
        url="https://example.com/stable",
        context=SnapshotContext(run_id=None),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    second = capture_page(
        url="https://example.com/stable",
        context=SnapshotContext(run_id=None),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    assert first.content_sha256 == second.content_sha256


def test_capture_page_proof_debug_stores_artifact() -> None:
    provider = StubSnapshotProvider()
    repo = InMemorySnapshotRepo()
    store = InMemoryArtifactStore()
    result = capture_page(
        url="https://example.com/debug",
        context=SnapshotContext(run_id=None),
        provider_config=SnapshotProviderConfig(
            provider_name="stub",
            flags={"proof_mode": "debug"},
        ),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    assert result.content_ref is not None
    assert result.content_sha256 is not None
    assert result.content_size_bytes is not None


def test_capture_page_idempotent_within_run() -> None:
    provider = StubSnapshotProvider()
    repo = InMemorySnapshotRepo()
    store = InMemoryArtifactStore()
    run_id = uuid.uuid4()
    first = capture_page(
        url="https://example.com/idempotent",
        context=SnapshotContext(run_id=run_id),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    second = capture_page(
        url="https://example.com/idempotent",
        context=SnapshotContext(run_id=run_id),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    assert first.id == second.id
    assert len(repo.snapshots) == 1


def test_capture_page_allows_same_url_across_runs() -> None:
    provider = StubSnapshotProvider()
    repo = InMemorySnapshotRepo()
    store = InMemoryArtifactStore()
    first = capture_page(
        url="https://example.com/same",
        context=SnapshotContext(run_id=uuid.uuid4()),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    second = capture_page(
        url="https://example.com/same",
        context=SnapshotContext(run_id=uuid.uuid4()),
        provider_config=SnapshotProviderConfig(provider_name="stub"),
        provider=provider,
        repository=repo,
        artifact_store=store,
    )
    assert first.id != second.id
    assert len(repo.snapshots) == 2
