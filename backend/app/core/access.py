"""Account-status and administrator authorization dependencies."""

import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import record_admin_audit_event
from app.core.security import AuthUser, get_current_user
from app.db.session import get_db
from app.models.admin import AdminUser, UserAccountStatus
from app.models.profile import UserProfile

SUSPENDED_MESSAGE = "This account is suspended."
ADMIN_REQUIRED_MESSAGE = "Administrator access required."
VERIFICATION_REQUIRED_MESSAGE = "Email verification is required."
PROFILE_REQUIRED_MESSAGE = "Profile completion required."

logger = logging.getLogger(__name__)


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"success": False, "message": message},
    )


def get_active_user(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AuthUser:
    """Return the authenticated user unless the account is suspended."""
    account_status = session.get(UserAccountStatus, user.id)
    if account_status is not None and account_status.status == "suspended":
        raise _forbidden(SUSPENDED_MESSAGE)
    return user


def require_verified_email(
    user: AuthUser = Depends(get_active_user),
    session: Session = Depends(get_db),
) -> AuthUser:
    """Return the active user only when their email is verified.

    Supabase access tokens do not always carry an ``email_verified``
    claim. On PostgreSQL, the authoritative confirmation state is read
    from Supabase's ``auth.users.email_confirmed_at``. Local SQLite tests
    use the signed JWT claim instead. Verification failures deny access
    rather than assuming the address is verified.
    """
    if user.email_verified:
        return user

    if session.get_bind().dialect.name == "postgresql":
        try:
            confirmed_at = session.execute(
                text(
                    "SELECT email_confirmed_at FROM auth.users "
                    "WHERE id = :user_id"
                ),
                {"user_id": user.id},
            ).scalar_one_or_none()
        except Exception as exc:
            session.rollback()
            logger.warning(
                "email_verification_lookup_failed error_type=%s",
                type(exc).__name__,
            )
            raise _forbidden(
                VERIFICATION_REQUIRED_MESSAGE
            ) from exc
        if confirmed_at is not None:
            return user.model_copy(update={"email_verified": True})

    raise _forbidden(VERIFICATION_REQUIRED_MESSAGE)


def require_complete_profile(
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
) -> AuthUser:
    """Return the user only when a complete required profile exists."""
    profile = session.get(UserProfile, user.id)
    if profile is None or not profile.full_name.strip():
        raise _forbidden(PROFILE_REQUIRED_MESSAGE)
    return user


def _audit_denied_admin_access(
    session: Session,
    request: Request,
    user: AuthUser,
    *,
    actor_is_admin: bool,
    admin_user_id: str | None,
    reason: str,
) -> None:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or "<unmatched>"
    try:
        record_admin_audit_event(
            session,
            actor_user_id=user.id,
            admin_user_id=admin_user_id,
            actor_is_admin=actor_is_admin,
            action="admin.access_denied",
            target_type="route",
            target_id=route_path,
            success=False,
            reason=reason,
            details={
                "request_id": getattr(request.state, "request_id", None),
            },
        )
    except Exception as exc:
        # A failure to record a denial must not turn a 403 into a 500.
        session.rollback()
        logger.warning(
            "admin_audit_denied_failed error_type=%s", type(exc).__name__
        )


def require_admin(
    request: Request,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AuthUser:
    """Return the authenticated active user only if they are an admin."""
    account_status = session.get(UserAccountStatus, user.id)
    if account_status is not None and account_status.status == "suspended":
        admin = session.get(AdminUser, user.id)
        _audit_denied_admin_access(
            session,
            request,
            user,
            actor_is_admin=admin is not None,
            admin_user_id=user.id if admin is not None else None,
            reason=SUSPENDED_MESSAGE,
        )
        raise _forbidden(SUSPENDED_MESSAGE)

    if session.get(AdminUser, user.id) is None:
        _audit_denied_admin_access(
            session,
            request,
            user,
            actor_is_admin=False,
            admin_user_id=None,
            reason=ADMIN_REQUIRED_MESSAGE,
        )
        raise _forbidden(ADMIN_REQUIRED_MESSAGE)

    return user
