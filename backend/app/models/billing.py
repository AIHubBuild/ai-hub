"""Stripe billing state.

User identities are owned by Supabase Auth. These tables reference the
Supabase user UUID and store only the billing identifiers and subscription
state needed for backend-authoritative entitlement checks.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StripeCustomer(Base):
    __tablename__ = "stripe_customers"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    trial_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    trial_checkout_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class StripeSubscription(Base):
    __tablename__ = "stripe_subscriptions"

    stripe_subscription_id: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), nullable=False, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cancel_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
