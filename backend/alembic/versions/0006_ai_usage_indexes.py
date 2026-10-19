"""add sanitized AI error category and usage indexes

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18

Additive read-model support for the private admin dashboard. Existing
run records keep their raw error text for operational persistence, but
the admin API never returns it. ``error_category`` is the sanitized
exception type for new failed runs.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_run_records",
        sa.Column("error_category", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_ai_run_records_created_at",
        "ai_run_records",
        ["created_at"],
    )
    op.create_index(
        "ix_ai_run_records_domain_created_at",
        "ai_run_records",
        ["domain", "created_at"],
    )
    op.create_index(
        "ix_ai_run_records_status_created_at",
        "ai_run_records",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_ai_run_records_error_category_created_at",
        "ai_run_records",
        ["error_category", "created_at"],
    )
    op.create_index(
        "ix_ai_run_records_user_id_created_at",
        "ai_run_records",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_run_records_user_id_created_at",
        table_name="ai_run_records",
    )
    op.drop_index(
        "ix_ai_run_records_error_category_created_at",
        table_name="ai_run_records",
    )
    op.drop_index(
        "ix_ai_run_records_status_created_at",
        table_name="ai_run_records",
    )
    op.drop_index(
        "ix_ai_run_records_domain_created_at",
        table_name="ai_run_records",
    )
    op.drop_index(
        "ix_ai_run_records_created_at",
        table_name="ai_run_records",
    )
    with op.batch_alter_table("ai_run_records") as batch_op:
        batch_op.drop_column("error_category")
