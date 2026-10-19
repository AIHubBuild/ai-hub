"""add audit actors and allow denied non-admin attempts

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18

Extends the administrative audit table so authenticated denied attempts
can be recorded. Unauthenticated attempts have no trusted actor and
remain in metadata-only request logs.

The downgrade requires no rows with a NULL admin_user_id; otherwise the
NOT NULL constraint cannot be restored.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("actor_user_id", sa.Uuid(as_uuid=False), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "actor_is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.alter_column(
            "admin_user_id",
            existing_type=sa.Uuid(as_uuid=False),
            nullable=True,
        )
        batch_op.create_index(
            "ix_admin_audit_events_actor_user_id",
            ["actor_user_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_audit_events") as batch_op:
        batch_op.drop_index("ix_admin_audit_events_actor_user_id")
        batch_op.drop_column("actor_is_admin")
        batch_op.drop_column("actor_user_id")
        batch_op.alter_column(
            "admin_user_id",
            existing_type=sa.Uuid(as_uuid=False),
            nullable=False,
        )
