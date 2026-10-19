"""Administrative audit helpers.

``add_admin_audit_event`` participates in the caller's transaction and
must be used with privileged database mutations. ``record_admin_audit_event``
commits immediately for standalone events such as denied access attempts.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.admin import AdminAuditEvent


def add_admin_audit_event(
    session: Session,
    *,
    action: str,
    target_type: str,
    actor_user_id: str | None = None,
    admin_user_id: str | None = None,
    actor_is_admin: bool = False,
    target_id: str | None = None,
    success: bool = True,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditEvent:
    """Add an audit event without committing the caller's transaction."""
    event = AdminAuditEvent(
        actor_user_id=actor_user_id,
        admin_user_id=admin_user_id,
        actor_is_admin=actor_is_admin,
        action=action,
        target_type=target_type,
        target_id=target_id,
        success=success,
        reason=reason,
        details=details,
    )
    session.add(event)
    session.flush()
    return event


def record_admin_audit_event(
    session: Session,
    *,
    action: str,
    target_type: str,
    actor_user_id: str | None = None,
    admin_user_id: str | None = None,
    actor_is_admin: bool = False,
    target_id: str | None = None,
    success: bool = True,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditEvent:
    """Persist a standalone audit event in its own transaction."""
    event = add_admin_audit_event(
        session,
        action=action,
        target_type=target_type,
        actor_user_id=actor_user_id,
        admin_user_id=admin_user_id,
        actor_is_admin=actor_is_admin,
        target_id=target_id,
        success=success,
        reason=reason,
        details=details,
    )
    session.commit()
    session.refresh(event)
    return event
