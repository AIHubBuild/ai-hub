"""create manual user entitlements

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_entitlements",
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("granted_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tier IN ('free', 'pro')",
            name="ck_user_entitlements_tier",
        ),
        sa.CheckConstraint(
            "source = 'manual'",
            name="ck_user_entitlements_source",
        ),
    )
    op.create_index("ix_user_entitlements_tier", "user_entitlements", ["tier"])
    op.create_index(
        "ix_user_entitlements_updated_at",
        "user_entitlements",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_entitlements_updated_at", table_name="user_entitlements"
    )
    op.drop_index("ix_user_entitlements_tier", table_name="user_entitlements")
    op.drop_table("user_entitlements")
