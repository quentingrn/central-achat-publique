"""llm audit fields + agent_version

Revision ID: 20260130_0003
Revises: 20260130_0002
Create Date: 2026-01-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260130_0003"
down_revision = "20260130_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("compare_runs", sa.Column("agent_version", sa.String(length=128)))

    op.add_column("prompts", sa.Column("content_hash", sa.String(length=64)))

    op.add_column("llm_runs", sa.Column("prompt_content", sa.String))
    op.add_column("llm_runs", sa.Column("prompt_hash", sa.String(length=64)))
    op.add_column("llm_runs", sa.Column("model_params", postgresql.JSONB()))
    op.add_column("llm_runs", sa.Column("json_schema", postgresql.JSONB()))
    op.add_column("llm_runs", sa.Column("json_schema_hash", sa.String(length=64)))
    op.add_column("llm_runs", sa.Column("output_validated_json", postgresql.JSONB()))
    op.add_column("llm_runs", sa.Column("validation_errors", postgresql.JSONB()))


def downgrade() -> None:
    raise RuntimeError(
        "Destructive downgrades are forbidden. Provide a plan and justification in CONTEXT_SNAPSHOT.md."
    )
