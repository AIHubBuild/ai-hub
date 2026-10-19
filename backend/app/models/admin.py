"""Administrative authorization and account-safety models.

These tables are additive. User identities remain owned by Supabase Auth;
these rows reference Supabase user UUIDs without duplicating auth data.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True
    )


class UserAccountStatus(Base):
    __tablename__ = "user_account_status"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_user_account_status_status",
        ),
    )

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", index=True
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"

    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True
    )
    admin_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True
    )
    actor_is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class AdminIncident(Base):
    __tablename__ = "admin_incidents"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_admin_incidents_priority",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'waiting_for_information', "
            "'resolved', 'closed')",
            name="ck_admin_incidents_status",
        ),
    )

    incident_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    linked_run_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True
    )
    linked_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", index=True
    )
    assigned_admin_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserEntitlement(Base):
    __tablename__ = "user_entitlements"
    __table_args__ = (
        CheckConstraint(
            "tier IN ('free', 'pro')",
            name="ck_user_entitlements_tier",
        ),
        CheckConstraint(
            "source = 'manual'",
            name="ck_user_entitlements_source",
        ),
    )

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual"
    )
    granted_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True,
    )
