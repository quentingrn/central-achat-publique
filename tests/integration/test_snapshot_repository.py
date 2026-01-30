import uuid
from datetime import UTC, datetime

import pytest

from modules.discovery_compare.infrastructure.persistence.models import PageSnapshot, Product
from modules.snapshot.adapters.schemas import ExtractionMethod, PageSnapshotResult, SnapshotStatus
from modules.snapshot.infrastructure.persistence import SqlSnapshotRepository
from shared.db.session import get_session
from tests.integration.db_utils import db_available


@pytest.mark.integration
def test_snapshot_repository_persists_fields() -> None:
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
        snapshot = PageSnapshotResult(
            url=url,
            final_url=url,
            provider="stub",
            captured_at=datetime.now(UTC),
            http_status=200,
            extraction_method=ExtractionMethod.minimal,
            status=SnapshotStatus.partial,
            extracted_json={"url": url},
            digest_json={"url": url},
            content_ref="mem://ref",
            content_sha256="abc",
            content_size_bytes=123,
            content_type="text/html",
            rules_version="v1",
            missing_critical_json={"brand": True},
            digest_hash="digest",
            errors_json=None,
        )
        repo = SqlSnapshotRepository(session=session, default_product_id=product.id)
        snapshot_id = repo.append_snapshot(snapshot)

        row = session.get(PageSnapshot, snapshot_id)
        assert row is not None
        assert row.final_url == url
        assert row.provider == "stub"
        assert row.extraction_method == "minimal"
        assert row.extraction_status == "partial"
        assert row.content_ref == "mem://ref"
        assert row.content_sha256 == "abc"
        assert row.content_size_bytes == 123
        assert row.content_type == "text/html"
        assert row.rules_version == "v1"
        assert row.missing_critical_json == {"brand": True}
        assert row.digest_hash == "digest"
    finally:
        session.close()
