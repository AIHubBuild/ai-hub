"""create ai_run_records

Revision ID: 0001
Revises:
Create Date: 2026-09-27

The shared AI run-records table (`docs/09_Migration_Analysis.md` §5
Phase 1 item 8): every AI interaction persisted in structured form.
UUID primary keys per `docs/05_Database_Design.md` §4.2. Dialect-
portable types (Uuid, JSON) so the migration applies to SQLite
(development) and PostgreSQL (Supabase) alike.
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_run_records",
        sa.Column("run_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("workflow_id", sa.String(length=200), nullable=False),
        sa.Column("prompt_id", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("thread_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("input_state", sa.JSON(), nullable=False),
        sa.Column("output_state", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_run_records_user_id", "ai_run_records", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_run_records_user_id", table_name="ai_run_records")
    op.drop_table("ai_run_records")
