"""Administrator access and read-model endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.access import require_admin
from app.core.security import AuthUser
from app.db.session import get_db
from app.domains.admin import mutations, read_models
from app.domains.admin.schemas import (
    EntitlementUpdate,
    IncidentCreate,
    IncidentUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])

Window = Literal["24h", "7d", "30d"]
Assistant = Literal["resume_ats", "support_copilot"]
RunStatus = Literal["success", "error"]
IncidentStatus = Literal[
    "open", "investigating", "waiting_for_information", "resolved", "closed"
]
IncidentPriority = Literal["low", "medium", "high", "critical"]
EntitlementTier = Literal["free", "pro"]


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"success": False, "message": message},
    )


@router.get("/me")
def admin_me(user: AuthUser = Depends(require_admin)) -> dict:
    return {
        "success": True,
        "message": "Administrator access granted.",
        "data": {"user_id": user.id, "email": user.email},
    }


@router.get("/usage")
def admin_usage(
    window: Window = "7d",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    assistant: Assistant | None = None,
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    window_start, window_end = read_models.resolve_window(
        window, start, end
    )
    return {
        "success": True,
        "message": "AI usage retrieved.",
        "data": read_models.usage_summary(
            session,
            start=window_start,
            end=window_end,
            assistant=assistant,
        ),
    }


@router.get("/requests")
def admin_requests(
    window: Window = "30d",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    assistant: Assistant | None = None,
    status: RunStatus | None = None,
    run_id: UUID | None = None,
    user_id: UUID | None = None,
    error_category: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=read_models.MAX_PAGE_SIZE),
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    window_start, window_end = read_models.resolve_window(
        window, start, end
    )
    return {
        "success": True,
        "message": "AI requests retrieved.",
        "data": read_models.list_requests(
            session,
            start=window_start,
            end=window_end,
            assistant=assistant,
            status=status,
            run_id=str(run_id) if run_id else None,
            user_id=str(user_id) if user_id else None,
            error_category=error_category,
            page=page,
            page_size=page_size,
        ),
    }


@router.get("/requests/{run_id}")
def admin_request_detail(
    run_id: UUID,
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    data = read_models.get_request_detail(session, str(run_id))
    if data is None:
        raise _not_found("AI request not found.")
    return {
        "success": True,
        "message": "AI request retrieved.",
        "data": data,
    }


@router.get("/audit")
def admin_audit(
    window: Window = "30d",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    actor_user_id: UUID | None = None,
    action: str | None = Query(None, max_length=100),
    target_type: str | None = Query(None, max_length=50),
    success: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=read_models.MAX_PAGE_SIZE),
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    window_start, window_end = read_models.resolve_window(
        window, start, end
    )
    return {
        "success": True,
        "message": "Administrative audit events retrieved.",
        "data": read_models.list_audit_events(
            session,
            start=window_start,
            end=window_end,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            action=action,
            target_type=target_type,
            success=success,
            page=page,
            page_size=page_size,
        ),
    }


@router.get("/incidents")
def admin_incidents(
    status: IncidentStatus | None = None,
    priority: IncidentPriority | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=read_models.MAX_PAGE_SIZE),
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    return {
        "success": True,
        "message": "Support incidents retrieved.",
        "data": read_models.list_incidents(
            session,
            status=status,
            priority=priority,
            page=page,
            page_size=page_size,
        ),
    }


@router.post("/incidents", status_code=201)
def admin_create_incident(
    body: IncidentCreate,
    admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    try:
        incident = mutations.create_incident(session, admin, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "message": str(exc)},
        ) from exc
    return {
        "success": True,
        "message": "Support incident created.",
        "data": mutations.incident_to_dict(incident),
    }


@router.get("/incidents/{incident_id}")
def admin_incident_detail(
    incident_id: UUID,
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    incident = read_models.get_incident(session, str(incident_id))
    if incident is None:
        raise _not_found("Support incident not found.")
    history = [
        read_models.audit_event_summary(event)
        for event in mutations.incident_history(session, str(incident_id))
    ]
    data = read_models.incident_detail(incident)
    data["history"] = history
    return {
        "success": True,
        "message": "Support incident retrieved.",
        "data": data,
    }


@router.patch("/incidents/{incident_id}")
def admin_update_incident(
    incident_id: UUID,
    body: IncidentUpdate,
    admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    try:
        incident = mutations.update_incident(
            session, admin, str(incident_id), body
        )
    except mutations.IncidentNotFoundError as exc:
        raise _not_found("Support incident not found.") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "message": str(exc)},
        ) from exc
    return {
        "success": True,
        "message": "Support incident updated.",
        "data": mutations.incident_to_dict(incident),
    }


@router.get("/entitlements")
def admin_entitlements(
    tier: EntitlementTier | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=read_models.MAX_PAGE_SIZE),
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    return {
        "success": True,
        "message": "Manual entitlements retrieved.",
        "data": read_models.list_entitlements(
            session,
            tier=tier,
            page=page,
            page_size=page_size,
        ),
    }


@router.get("/users/{user_id}/entitlement")
def admin_user_entitlement(
    user_id: UUID,
    _admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    entitlement = read_models.get_entitlement(session, str(user_id))
    if entitlement is None:
        raise _not_found("Manual entitlement not found.")
    return {
        "success": True,
        "message": "Manual entitlement retrieved.",
        "data": mutations.entitlement_to_dict(entitlement),
    }


@router.put("/users/{user_id}/entitlement")
def admin_set_user_entitlement(
    user_id: UUID,
    body: EntitlementUpdate,
    admin: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    entitlement = mutations.upsert_entitlement(
        session, admin, str(user_id), body
    )
    return {
        "success": True,
        "message": "Manual entitlement updated.",
        "data": mutations.entitlement_to_dict(entitlement),
    }
