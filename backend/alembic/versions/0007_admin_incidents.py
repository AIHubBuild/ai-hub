"""create administrative incidents

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_incidents",
        sa.Column("incident_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("linked_run_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("linked_user_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_admin_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_admin_incidents_priority",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'waiting_for_information', "
            "'resolved', 'closed')",
            name="ck_admin_incidents_status",
        ),
    )
    op.create_index(
        "ix_admin_incidents_linked_run_id",
        "admin_incidents",
        ["linked_run_id"],
    )
    op.create_index(
        "ix_admin_incidents_linked_user_id",
        "admin_incidents",
        ["linked_user_id"],
    )
    op.create_index(
        "ix_admin_incidents_assigned_admin_id",
        "admin_incidents",
        ["assigned_admin_id"],
    )
    op.create_index(
        "ix_admin_incidents_status",
        "admin_incidents",
        ["status"],
    )
    op.create_index(
        "ix_admin_incidents_created_at",
        "admin_incidents",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_incidents_created_at", table_name="admin_incidents")
    op.drop_index("ix_admin_incidents_status", table_name="admin_incidents")
    op.drop_index(
        "ix_admin_incidents_assigned_admin_id", table_name="admin_incidents"
    )
    op.drop_index(
        "ix_admin_incidents_linked_user_id", table_name="admin_incidents"
    )
    op.drop_index(
        "ix_admin_incidents_linked_run_id", table_name="admin_incidents"
    )
    op.drop_table("admin_incidents")
