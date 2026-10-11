"""create support_sessions and support_tickets

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11

Support Copilot domain tables (`docs/09_Migration_Analysis.md` §4):
persisted support conversations and the ticket lifecycle, both scoped
to the authenticated user. UUID primary keys per
`docs/05_Database_Design.md` §4.2.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_sessions",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_support_sessions_user_id", "support_sessions", ["user_id"]
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("session_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("assigned_team", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["support_sessions.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_support_tickets_session_id", "support_tickets", ["session_id"]
    )
    op.create_index(
        "ix_support_tickets_user_id", "support_tickets", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_session_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("ix_support_sessions_user_id", table_name="support_sessions")
    op.drop_table("support_sessions")
