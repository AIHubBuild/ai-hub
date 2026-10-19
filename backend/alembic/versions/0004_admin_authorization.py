"""create admin authorization, account status, and audit tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18

Additive Phase 2 foundation: database-backed administrator identities,
account suspension state, and append-oriented administrative audit
events. No existing tables are altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=True),
    )

    op.create_table(
        "user_account_status",
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_user_account_status_status",
        ),
    )
    op.create_index(
        "ix_user_account_status_status",
        "user_account_status",
        ["status"],
    )

    op.create_table(
        "admin_audit_events",
        sa.Column("event_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("admin_user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_admin_audit_events_admin_user_id",
        "admin_audit_events",
        ["admin_user_id"],
    )
    op.create_index(
        "ix_admin_audit_events_created_at",
        "admin_audit_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_audit_events_created_at",
        table_name="admin_audit_events",
    )
    op.drop_index(
        "ix_admin_audit_events_admin_user_id",
        table_name="admin_audit_events",
    )
    op.drop_table("admin_audit_events")
    op.drop_index(
        "ix_user_account_status_status",
        table_name="user_account_status",
    )
    op.drop_table("user_account_status")
    op.drop_table("admin_users")
