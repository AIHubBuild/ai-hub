"""Bounded read models for the Phase 2 admin dashboard."""

from datetime import datetime, timedelta, timezone
from math import ceil
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.admin import AdminAuditEvent, AdminIncident, UserEntitlement
from app.models.ai_run_record import AIRunRecord

WINDOW_DAYS = {"24h": 1, "7d": 7, "30d": 30}
MAX_RANGE_DAYS = 366
MAX_PAGE_SIZE = 100

_EXCEPTION_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,99}$")


def _bad_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"success": False, "message": message},
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_window(
    window: str,
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if start is not None or end is not None:
        end_at = _as_utc(end) if end is not None else now
        start_at = (
            _as_utc(start)
            if start is not None
            else end_at - timedelta(days=WINDOW_DAYS.get(window, 7))
        )
    else:
        end_at = now
        start_at = end_at - timedelta(days=WINDOW_DAYS.get(window, 7))

    if start_at > end_at:
        raise _bad_request("The start time must be before the end time.")
    if end_at - start_at > timedelta(days=MAX_RANGE_DAYS):
        raise _bad_request("The requested time range is too large.")
    return start_at, end_at


def safe_error_category(record: AIRunRecord) -> str | None:
    if record.error_category:
        return record.error_category
    if record.status != "error" or not record.error:
        return None
    prefix = record.error.split(":", 1)[0].strip()
    return prefix if _EXCEPTION_TYPE.fullmatch(prefix) else "unknown"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def safe_run_item(record: AIRunRecord, *, detail: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "run_id": record.run_id,
        "user_id": record.user_id,
        "assistant": record.domain,
        "workflow_id": record.workflow_id,
        "model": record.model,
        "status": record.status,
        "error_category": safe_error_category(record),
        "latency_ms": record.latency_ms,
        "created_at": _iso(record.created_at),
    }
    if detail:
        item.update(
            {
                "prompt_id": record.prompt_id,
                "prompt_version": record.prompt_version,
                "thread_id": record.thread_id,
            }
        )
    return item


def usage_summary(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    assistant: str | None,
) -> dict[str, Any]:
    filters = [
        AIRunRecord.created_at >= start,
        AIRunRecord.created_at <= end,
    ]
    if assistant:
        filters.append(AIRunRecord.domain == assistant)

    total = session.query(AIRunRecord).filter(*filters).count()
    successful = (
        session.query(AIRunRecord)
        .filter(*filters, AIRunRecord.status == "success")
        .count()
    )
    failed = total - successful

    average_latency, maximum_latency = (
        session.query(
            func.avg(AIRunRecord.latency_ms),
            func.max(AIRunRecord.latency_ms),
        )
        .filter(*filters)
        .one()
    )

    rows = (
        session.query(
            AIRunRecord.domain,
            func.count(AIRunRecord.run_id),
            func.sum(
                case((AIRunRecord.status == "success", 1), else_=0)
            ),
            func.avg(AIRunRecord.latency_ms),
        )
        .filter(*filters)
        .group_by(AIRunRecord.domain)
        .order_by(AIRunRecord.domain)
        .all()
    )

    by_assistant = []
    for domain, count, success_count, avg_latency in rows:
        by_assistant.append(
            {
                "assistant": domain,
                "total_requests": count,
                "successful_requests": int(success_count or 0),
                "failed_requests": count - int(success_count or 0),
                "average_latency_ms": (
                    round(float(avg_latency), 1)
                    if avg_latency is not None
                    else None
                ),
            }
        )

    return {
        "window_start": _iso(start),
        "window_end": _iso(end),
        "total_requests": total,
        "successful_requests": successful,
        "failed_requests": failed,
        "success_rate": round(successful / total * 100, 2) if total else 0.0,
        "failure_rate": round(failed / total * 100, 2) if total else 0.0,
        "average_latency_ms": (
            round(float(average_latency), 1)
            if average_latency is not None
            else None
        ),
        "max_latency_ms": maximum_latency,
        "by_assistant": by_assistant,
        "token_usage_available": False,
    }


def list_requests(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    assistant: str | None,
    status: str | None,
    run_id: str | None,
    user_id: str | None,
    error_category: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    filters = [
        AIRunRecord.created_at >= start,
        AIRunRecord.created_at <= end,
    ]
    if assistant:
        filters.append(AIRunRecord.domain == assistant)
    if status:
        filters.append(AIRunRecord.status == status)
    if run_id:
        filters.append(AIRunRecord.run_id == run_id)
    if user_id:
        filters.append(AIRunRecord.user_id == user_id)
    if error_category:
        filters.append(AIRunRecord.error_category == error_category)

    query = session.query(AIRunRecord).filter(*filters)
    total = query.count()
    rows = (
        query.order_by(AIRunRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "items": [safe_run_item(row) for row in rows],
    }


def get_request_detail(
    session: Session, run_id: str
) -> dict[str, Any] | None:
    record = session.get(AIRunRecord, run_id)
    return safe_run_item(record, detail=True) if record is not None else None


def list_audit_events(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    actor_user_id: str | None,
    action: str | None,
    target_type: str | None,
    success: bool | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    filters = [
        AdminAuditEvent.created_at >= start,
        AdminAuditEvent.created_at <= end,
    ]
    if actor_user_id:
        filters.append(AdminAuditEvent.actor_user_id == actor_user_id)
    if action:
        filters.append(AdminAuditEvent.action == action)
    if target_type:
        filters.append(AdminAuditEvent.target_type == target_type)
    if success is not None:
        filters.append(AdminAuditEvent.success == success)

    query = session.query(AdminAuditEvent).filter(*filters)
    total = query.count()
    rows = (
        query.order_by(AdminAuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "items": [
            {
                "event_id": row.event_id,
                "actor_user_id": row.actor_user_id,
                "admin_user_id": row.admin_user_id,
                "actor_is_admin": row.actor_is_admin,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "success": row.success,
                "reason": row.reason,
                "details": row.details,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ],
    }


def incident_summary(incident) -> dict[str, Any]:
    return {
        "incident_id": incident.incident_id,
        "linked_run_id": incident.linked_run_id,
        "linked_user_id": incident.linked_user_id,
        "title": incident.title,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "assigned_admin_id": incident.assigned_admin_id,
        "created_at": _iso(incident.created_at),
        "updated_at": _iso(incident.updated_at),
        "resolved_at": _iso(incident.resolved_at),
    }


def incident_detail(incident) -> dict[str, Any]:
    data = incident_summary(incident)
    data.update(
        {
            "description": incident.description,
            "created_by": incident.created_by,
            "resolution_summary": incident.resolution_summary,
        }
    )
    return data


def list_incidents(
    session: Session,
    *,
    status: str | None,
    priority: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = session.query(AdminIncident)
    if status:
        query = query.filter(AdminIncident.status == status)
    if priority:
        query = query.filter(AdminIncident.priority == priority)
    total = query.count()
    rows = (
        query.order_by(AdminIncident.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "items": [incident_summary(row) for row in rows],
    }


def get_incident(session: Session, incident_id: str):
    return session.get(AdminIncident, incident_id)


def audit_event_summary(event: AdminAuditEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "actor_user_id": event.actor_user_id,
        "admin_user_id": event.admin_user_id,
        "actor_is_admin": event.actor_is_admin,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "success": event.success,
        "reason": event.reason,
        "details": event.details,
        "created_at": _iso(event.created_at),
    }


def entitlement_summary(entitlement) -> dict[str, Any]:
    return {
        "user_id": entitlement.user_id,
        "tier": entitlement.tier,
        "limits": entitlement.limits,
        "source": entitlement.source,
        "granted_by": entitlement.granted_by,
        "reason": entitlement.reason,
        "created_at": _iso(entitlement.created_at),
        "updated_at": _iso(entitlement.updated_at),
    }


def list_entitlements(
    session: Session,
    *,
    tier: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = session.query(UserEntitlement)
    if tier:
        query = query.filter(UserEntitlement.tier == tier)
    total = query.count()
    rows = (
        query.order_by(UserEntitlement.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "items": [entitlement_summary(row) for row in rows],
    }


def get_entitlement(session: Session, user_id: str):
    return session.get(UserEntitlement, user_id)
