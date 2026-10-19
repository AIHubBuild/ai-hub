"""Administrative mutations with transactional audit events."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import add_admin_audit_event, record_admin_audit_event
from app.core.security import AuthUser
from app.domains.admin.schemas import (
    EntitlementUpdate,
    IncidentCreate,
    IncidentUpdate,
)
from app.models.admin import (
    AdminAuditEvent,
    AdminIncident,
    AdminUser,
    UserEntitlement,
)
from app.models.ai_run_record import AIRunRecord

logger = logging.getLogger(__name__)


class IncidentNotFoundError(KeyError):
    """No incident exists under the requested id."""


def _record_failure(
    session: Session,
    admin: AuthUser,
    *,
    action: str,
    target_type: str,
    target_id: str | None,
    reason_code: str,
) -> None:
    try:
        record_admin_audit_event(
            session,
            actor_user_id=admin.id,
            admin_user_id=admin.id,
            actor_is_admin=True,
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=False,
            reason=reason_code,
            details={"reason_code": reason_code},
        )
    except Exception as exc:
        session.rollback()
        logger.warning(
            "admin_audit_failure_failed error_type=%s", type(exc).__name__
        )


def incident_to_dict(incident: AdminIncident) -> dict:
    return {
        "incident_id": incident.incident_id,
        "linked_run_id": incident.linked_run_id,
        "linked_user_id": incident.linked_user_id,
        "title": incident.title,
        "description": incident.description,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "assigned_admin_id": incident.assigned_admin_id,
        "created_by": incident.created_by,
        "resolution_summary": incident.resolution_summary,
        "resolved_at": (
            incident.resolved_at.isoformat()
            if incident.resolved_at is not None
            else None
        ),
        "created_at": (
            incident.created_at.isoformat()
            if incident.created_at is not None
            else None
        ),
        "updated_at": (
            incident.updated_at.isoformat()
            if incident.updated_at is not None
            else None
        ),
    }


def entitlement_to_dict(entitlement: UserEntitlement) -> dict:
    return {
        "user_id": entitlement.user_id,
        "tier": entitlement.tier,
        "limits": entitlement.limits,
        "source": entitlement.source,
        "granted_by": entitlement.granted_by,
        "reason": entitlement.reason,
        "created_at": (
            entitlement.created_at.isoformat()
            if entitlement.created_at is not None
            else None
        ),
        "updated_at": (
            entitlement.updated_at.isoformat()
            if entitlement.updated_at is not None
            else None
        ),
    }


def _validate_incident_links(
    session: Session, payload: IncidentCreate
) -> None:
    if payload.assigned_admin_id is not None:
        if session.get(AdminUser, str(payload.assigned_admin_id)) is None:
            raise ValueError("Assigned administrator not found.")
    if payload.linked_run_id is not None:
        if session.get(AIRunRecord, str(payload.linked_run_id)) is None:
            raise ValueError("Linked AI request not found.")


def create_incident(
    session: Session, admin: AuthUser, payload: IncidentCreate
) -> AdminIncident:
    try:
        _validate_incident_links(session, payload)
    except ValueError:
        _record_failure(
            session,
            admin,
            action="incident.create",
            target_type="incident",
            target_id=None,
            reason_code="invalid_reference",
        )
        raise
    incident = AdminIncident(
        linked_run_id=str(payload.linked_run_id) if payload.linked_run_id else None,
        linked_user_id=(
            str(payload.linked_user_id) if payload.linked_user_id else None
        ),
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category.strip(),
        priority=payload.priority,
        status=payload.status,
        assigned_admin_id=(
            str(payload.assigned_admin_id)
            if payload.assigned_admin_id
            else None
        ),
        created_by=admin.id,
    )
    try:
        session.add(incident)
        session.flush()
        add_admin_audit_event(
            session,
            actor_user_id=admin.id,
            admin_user_id=admin.id,
            actor_is_admin=True,
            action="incident.create",
            target_type="incident",
            target_id=incident.incident_id,
            success=True,
            details={
                "category": incident.category,
                "priority": incident.priority,
                "status": incident.status,
                "linked_run_id": incident.linked_run_id,
                "linked_user_id": incident.linked_user_id,
            },
        )
        session.commit()
        session.refresh(incident)
        return incident
    except Exception:
        session.rollback()
        _record_failure(
            session,
            admin,
            action="incident.create",
            target_type="incident",
            target_id=incident.incident_id,
            reason_code="database_error",
        )
        raise


def update_incident(
    session: Session,
    admin: AuthUser,
    incident_id: str,
    payload: IncidentUpdate,
) -> AdminIncident:
    incident = session.get(AdminIncident, incident_id)
    if incident is None:
        _record_failure(
            session,
            admin,
            action="incident.update",
            target_type="incident",
            target_id=incident_id,
            reason_code="not_found",
        )
        raise IncidentNotFoundError(incident_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValueError("No incident fields were provided.")
    if changes.get("assigned_admin_id") is not None:
        if session.get(
            AdminUser, str(changes["assigned_admin_id"])
        ) is None:
            _record_failure(
                session,
                admin,
                action="incident.update",
                target_type="incident",
                target_id=incident_id,
                reason_code="invalid_assignee",
            )
            raise ValueError("Assigned administrator not found.")

    next_status = changes.get("status", incident.status)
    next_summary = changes.get("resolution_summary", incident.resolution_summary)
    if next_status in {"resolved", "closed"} and not (
        next_summary and next_summary.strip()
    ):
        _record_failure(
            session,
            admin,
            action="incident.update",
            target_type="incident",
            target_id=incident_id,
            reason_code="resolution_summary_required",
        )
        raise ValueError(
            "A resolution summary is required before resolving or closing an incident."
        )

    audit_changes: dict = {}
    for field in ("status", "priority", "assigned_admin_id"):
        if field in changes:
            old_value = getattr(incident, field)
            new_value = changes[field]
            if field == "assigned_admin_id" and new_value is not None:
                new_value = str(new_value)
            if old_value != new_value:
                audit_changes[field] = {"old": old_value, "new": new_value}
                setattr(incident, field, new_value)

    if "resolution_summary" in changes:
        summary = changes["resolution_summary"]
        summary = summary.strip() if isinstance(summary, str) else summary
        if incident.resolution_summary != summary:
            audit_changes["resolution_summary_changed"] = True
            incident.resolution_summary = summary

    if "status" in changes:
        incident.resolved_at = (
            datetime.now(timezone.utc)
            if changes["status"] in {"resolved", "closed"}
            else None
        )

    try:
        add_admin_audit_event(
            session,
            actor_user_id=admin.id,
            admin_user_id=admin.id,
            actor_is_admin=True,
            action="incident.update",
            target_type="incident",
            target_id=incident.incident_id,
            success=True,
            details={"changes": audit_changes},
        )
        session.commit()
        session.refresh(incident)
        return incident
    except Exception:
        session.rollback()
        _record_failure(
            session,
            admin,
            action="incident.update",
            target_type="incident",
            target_id=incident_id,
            reason_code="database_error",
        )
        raise


def upsert_entitlement(
    session: Session,
    admin: AuthUser,
    user_id: str,
    payload: EntitlementUpdate,
) -> UserEntitlement:
    entitlement = session.get(UserEntitlement, user_id)
    old_tier = entitlement.tier if entitlement is not None else None
    old_limits = entitlement.limits if entitlement is not None else None

    if entitlement is None:
        entitlement = UserEntitlement(
            user_id=user_id,
            tier=payload.tier,
            limits=payload.limits,
            source="manual",
            granted_by=admin.id,
            reason=payload.reason.strip(),
        )
        session.add(entitlement)
    else:
        entitlement.tier = payload.tier
        entitlement.limits = payload.limits
        entitlement.granted_by = admin.id
        entitlement.reason = payload.reason.strip()

    try:
        add_admin_audit_event(
            session,
            actor_user_id=admin.id,
            admin_user_id=admin.id,
            actor_is_admin=True,
            action="entitlement.update",
            target_type="user_entitlement",
            target_id=user_id,
            success=True,
            details={
                "old_tier": old_tier,
                "new_tier": payload.tier,
                "limits_changed": old_limits != payload.limits,
            },
        )
        session.commit()
        session.refresh(entitlement)
        return entitlement
    except Exception:
        session.rollback()
        _record_failure(
            session,
            admin,
            action="entitlement.update",
            target_type="user_entitlement",
            target_id=user_id,
            reason_code="database_error",
        )
        raise


def incident_history(
    session: Session, incident_id: str
) -> list[AdminAuditEvent]:
    return (
        session.query(AdminAuditEvent)
        .filter(
            AdminAuditEvent.target_type == "incident",
            AdminAuditEvent.target_id == incident_id,
        )
        .order_by(AdminAuditEvent.created_at.asc())
        .all()
    )
