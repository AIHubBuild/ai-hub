"""Administrative service helpers."""

from app.core.audit import add_admin_audit_event, record_admin_audit_event

__all__ = ["add_admin_audit_event", "record_admin_audit_event"]
