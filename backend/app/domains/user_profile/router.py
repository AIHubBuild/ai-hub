"""Authenticated self-profile routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.access import require_verified_email
from app.core.security import AuthUser
from app.db.session import get_db
from app.domains.user_profile import service
from app.domains.user_profile.schemas import ProfileResponse, ProfileUpsert

router = APIRouter(prefix="/profile", tags=["profile"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"success": False, "message": "Profile not found."},
    )


@router.get("", response_model=ProfileResponse)
def read_profile(
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
) -> ProfileResponse:
    profile = service.get_profile(session, user.id)
    if profile is None:
        raise _not_found()
    return ProfileResponse(
        message="Profile retrieved.",
        data=service.profile_to_data(profile, user),
    )


@router.put("", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpsert,
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        profile = service.upsert_profile(session, user, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "message": str(exc)},
        ) from exc
    return ProfileResponse(
        message="Profile saved.",
        data=service.profile_to_data(profile, user),
    )
