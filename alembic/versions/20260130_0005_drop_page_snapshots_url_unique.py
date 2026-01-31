"""Drop unique constraint on page_snapshots.url

Revision ID: 20260130_0005
Revises: 20260130_0004
Create Date: 2026-01-30 00:05:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "20260130_0005"
down_revision = "20260130_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'page_snapshots_url_key'
            ) THEN
                ALTER TABLE page_snapshots DROP CONSTRAINT page_snapshots_url_key;
            ELSIF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_page_snapshots_url'
            ) THEN
                ALTER TABLE page_snapshots DROP CONSTRAINT uq_page_snapshots_url;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Destructive downgrades are forbidden. Provide a plan and justification in CONTEXT_SNAPSHOT.md."
    )
