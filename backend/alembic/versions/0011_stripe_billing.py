"""add Stripe billing state and subscription entitlements

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_entitlements") as batch_op:
        batch_op.drop_constraint(
            "ck_user_entitlements_source", type_="check"
        )
        batch_op.alter_column(
            "granted_by",
            existing_type=sa.Uuid(as_uuid=False),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_user_entitlements_source",
            "source IN ('manual', 'stripe')",
        )

    op.create_table(
        "stripe_customers",
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("trial_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_stripe_customers_stripe_customer_id",
        "stripe_customers",
        ["stripe_customer_id"],
        unique=True,
    )

    op.create_table(
        "stripe_subscriptions",
        sa.Column(
            "stripe_subscription_id", sa.String(length=255), primary_key=True
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column(
            "stripe_customer_id", sa.String(length=255), nullable=False
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("price_id", sa.String(length=255), nullable=True),
        sa.Column(
            "current_period_start", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "current_period_end", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), nullable=False
        ),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_stripe_subscriptions_user_id",
        "stripe_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_stripe_subscriptions_stripe_customer_id",
        "stripe_subscriptions",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_stripe_subscriptions_status",
        "stripe_subscriptions",
        ["status"],
    )

    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
    op.drop_index(
        "ix_stripe_subscriptions_status",
        table_name="stripe_subscriptions",
    )
    op.drop_index(
        "ix_stripe_subscriptions_stripe_customer_id",
        table_name="stripe_subscriptions",
    )
    op.drop_index(
        "ix_stripe_subscriptions_user_id",
        table_name="stripe_subscriptions",
    )
    op.drop_table("stripe_subscriptions")
    op.drop_index(
        "ix_stripe_customers_stripe_customer_id",
        table_name="stripe_customers",
    )
    op.drop_table("stripe_customers")

    with op.batch_alter_table("user_entitlements") as batch_op:
        batch_op.drop_constraint(
            "ck_user_entitlements_source", type_="check"
        )
        batch_op.alter_column(
            "granted_by",
            existing_type=sa.Uuid(as_uuid=False),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_user_entitlements_source",
            "source = 'manual'",
        )
