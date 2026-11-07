"""track pending trial checkout sessions

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stripe_customers",
        sa.Column(
            "trial_checkout_session_id", sa.String(length=255), nullable=True
        ),
    )
    op.add_column(
        "stripe_customers",
        sa.Column(
            "trial_checkout_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("stripe_customers", "trial_checkout_expires_at")
    op.drop_column("stripe_customers", "trial_checkout_session_id")
