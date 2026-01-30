"""Add snapshot metadata fields to page_snapshots.

Revision ID: 20260130_0004
Revises: 20260130_0003
Create Date: 2026-01-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260130_0004"
down_revision = "20260130_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page_snapshots",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("compare_runs.id")),
    )
    op.add_column("page_snapshots", sa.Column("final_url", sa.String(length=2048)))
    op.add_column("page_snapshots", sa.Column("provider", sa.String(length=128)))
    op.add_column("page_snapshots", sa.Column("http_status", sa.Integer()))
    op.add_column(
        "page_snapshots",
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.add_column("page_snapshots", sa.Column("extraction_method", sa.String(length=64)))
    op.add_column("page_snapshots", sa.Column("extraction_status", sa.String(length=32)))
    op.add_column("page_snapshots", sa.Column("rules_version", sa.String(length=64)))
    op.add_column("page_snapshots", sa.Column("content_ref", sa.String(length=2048)))
    op.add_column("page_snapshots", sa.Column("content_sha256", sa.String(length=64)))
    op.add_column("page_snapshots", sa.Column("content_size_bytes", sa.Integer()))
    op.add_column("page_snapshots", sa.Column("content_type", sa.String(length=255)))
    op.add_column("page_snapshots", sa.Column("errors_json", postgresql.JSONB()))
    op.add_column("page_snapshots", sa.Column("missing_critical_json", postgresql.JSONB()))
    op.add_column("page_snapshots", sa.Column("digest_hash", sa.String(length=64)))

    op.create_index("ix_page_snapshots_digest_hash", "page_snapshots", ["digest_hash"])
    op.create_index("ix_page_snapshots_run_id", "page_snapshots", ["run_id"])
    op.create_index("ix_page_snapshots_url_captured_at", "page_snapshots", ["url", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_page_snapshots_url_captured_at", table_name="page_snapshots")
    op.drop_index("ix_page_snapshots_run_id", table_name="page_snapshots")
    op.drop_index("ix_page_snapshots_digest_hash", table_name="page_snapshots")

    op.drop_column("page_snapshots", "digest_hash")
    op.drop_column("page_snapshots", "missing_critical_json")
    op.drop_column("page_snapshots", "errors_json")
    op.drop_column("page_snapshots", "content_type")
    op.drop_column("page_snapshots", "content_size_bytes")
    op.drop_column("page_snapshots", "content_sha256")
    op.drop_column("page_snapshots", "content_ref")
    op.drop_column("page_snapshots", "rules_version")
    op.drop_column("page_snapshots", "extraction_status")
    op.drop_column("page_snapshots", "extraction_method")
    op.drop_column("page_snapshots", "captured_at")
    op.drop_column("page_snapshots", "http_status")
    op.drop_column("page_snapshots", "provider")
    op.drop_column("page_snapshots", "final_url")
    op.drop_column("page_snapshots", "run_id")
