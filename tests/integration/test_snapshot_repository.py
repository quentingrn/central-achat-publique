import uuid

import pytest

from modules.discovery_compare.infrastructure.persistence.models import PageSnapshot, Product
from modules.snapshot.adapters.schemas import SnapshotContext, SnapshotProviderConfig
from modules.snapshot.application.facade import capture_page
from modules.snapshot.application.ports import CapturedPage, StoredArtifact
from modules.snapshot.infrastructure.persistence import SqlSnapshotRepository
from shared.db.session import get_session
from tests.integration.db_utils import db_available

HTML_JSONLD_OK = """
<html>
  <head>
    <script type="application/ld+json">
      {"@context": "https://schema.org", "@type": "Product", "name": "ACME Widget",
       "brand": {"@type": "Brand", "name": "ACME"}, "gtin13": "0123456789012"}
    </script>
  </head>
  <body></body>
</html>
"""

HTML_JSONLD_INVALID_DOM_OK = """
<html>
  <head>
    <script type="application/ld+json">{invalid json</script>
    <meta property="og:title" content="Fallback Title" />
  </head>
  <body></body>
</html>
"""

HTML_NO_JSONLD_NO_DOM = "<html><body><div>Nothing here</div></body></html>"


class HtmlSnapshotProvider:
    def __init__(self, html: str) -> None:
        self.html = html

    def capture(
        self, url: str, context: SnapshotContext, config: SnapshotProviderConfig
    ) -> CapturedPage:
        return CapturedPage(
            requested_url=url,
            final_url=url,
            http_status=200,
            content_bytes=self.html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
            metadata={"fixture": True},
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("html", "expected_method"),
    [
        (HTML_JSONLD_OK, "jsonld"),
        (HTML_JSONLD_INVALID_DOM_OK, "dom"),
        (HTML_NO_JSONLD_NO_DOM, "minimal"),
    ],
)
def test_snapshot_repository_persists_fields(html: str, expected_method: str) -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    session = get_session()
    try:
        product = Product(
            brand="ACME", model="X1", source_url=f"https://example.com/{uuid.uuid4()}"
        )
        session.add(product)
        session.commit()
        session.refresh(product)

        url = f"https://example.com/p/{uuid.uuid4()}"
        repo = SqlSnapshotRepository(session=session, default_product_id=product.id)
        provider = HtmlSnapshotProvider(html)

        class MemoryArtifactStore:
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

        store = MemoryArtifactStore()
        snapshot = capture_page(
            url=url,
            context=SnapshotContext(run_id=None),
            provider_config=SnapshotProviderConfig(
                provider_name="fixture",
                flags={"proof_mode": "debug"},
            ),
            provider=provider,
            repository=repo,
            artifact_store=store,
        )
        snapshot_id = snapshot.id

        row = session.get(PageSnapshot, snapshot_id)
        assert row is not None
        assert row.final_url == url
        assert row.provider == "fixture"
        assert row.extraction_method == expected_method
        assert row.extraction_status in {"ok", "partial", "indeterminate"}
        assert row.content_ref is not None
        assert row.content_sha256 is not None
        assert row.content_size_bytes is not None
        assert row.content_type == "text/html; charset=utf-8"
        assert row.extracted_json is not None
        assert row.extracted_json["extraction_version"] == "v1"
        assert row.extracted_json["method"] == expected_method
        assert "digest" in row.extracted_json
        assert row.digest_hash is not None
    finally:
        session.close()


@pytest.mark.integration
def test_snapshot_allows_same_url_multiple_rows() -> None:
    if not db_available():
        pytest.skip("Postgres not available")

    session = get_session()
    try:
        product = Product(
            brand="ACME", model="X2", source_url=f"https://example.com/{uuid.uuid4()}"
        )
        session.add(product)
        session.commit()
        session.refresh(product)

        url = f"https://example.com/repeat/{uuid.uuid4()}"
        repo = SqlSnapshotRepository(session=session, default_product_id=product.id)
        provider = HtmlSnapshotProvider(HTML_JSONLD_OK)

        class NoopArtifactStore:
            def put_bytes(self, content_bytes: bytes, content_type: str | None) -> StoredArtifact:
                return StoredArtifact(
                    content_ref=None,
                    sha256=None,
                    size_bytes=len(content_bytes),
                    content_type=content_type,
                )

        store = NoopArtifactStore()
        first = capture_page(
            url=url,
            context=SnapshotContext(run_id=None),
            provider_config=SnapshotProviderConfig(provider_name="fixture"),
            provider=provider,
            repository=repo,
            artifact_store=store,
        )
        second = capture_page(
            url=url,
            context=SnapshotContext(run_id=None),
            provider_config=SnapshotProviderConfig(provider_name="fixture"),
            provider=provider,
            repository=repo,
            artifact_store=store,
        )
        assert first.id != second.id
    finally:
        session.close()
