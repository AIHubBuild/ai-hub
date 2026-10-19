"""Profile persistence scoped to the authenticated Supabase user."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import AuthUser
from app.domains.user_profile.schemas import ProfileData, ProfileUpsert
from app.models.profile import UserProfile

CURRENT_TERMS_VERSION = "2026-10-19"
CURRENT_PRIVACY_VERSION = "2026-10-19"


def get_profile(session: Session, user_id: str) -> UserProfile | None:
    return session.get(UserProfile, user_id)


def upsert_profile(
    session: Session, user: AuthUser, payload: ProfileUpsert
) -> UserProfile:
    profile = session.get(UserProfile, user.id)
    now = datetime.now(timezone.utc)

    if profile is None:
        if not (payload.terms_accepted and payload.privacy_accepted):
            raise ValueError(
                "Terms of Service and Privacy Notice acceptance are required."
            )
        profile = UserProfile(
            user_id=user.id,
            full_name=payload.full_name,
            phone=payload.phone,
            country_code=payload.country_code,
            city=payload.city,
            career_goal=payload.career_goal,
            marketing_consent=payload.marketing_consent,
            terms_accepted_at=now,
            terms_version=CURRENT_TERMS_VERSION,
            privacy_accepted_at=now,
            privacy_version=CURRENT_PRIVACY_VERSION,
        )
        session.add(profile)
    else:
        profile.full_name = payload.full_name
        profile.phone = payload.phone
        profile.country_code = payload.country_code
        profile.city = payload.city
        profile.career_goal = payload.career_goal
        profile.marketing_consent = payload.marketing_consent

    session.commit()
    session.refresh(profile)
    return profile


def profile_to_data(profile: UserProfile, user: AuthUser) -> ProfileData:
    return ProfileData(
        user_id=profile.user_id,
        full_name=profile.full_name,
        phone=profile.phone,
        country_code=profile.country_code,
        city=profile.city,
        career_goal=profile.career_goal,
        marketing_consent=profile.marketing_consent,
        terms_accepted_at=profile.terms_accepted_at,
        terms_version=profile.terms_version,
        privacy_accepted_at=profile.privacy_accepted_at,
        privacy_version=profile.privacy_version,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        email=user.email,
        email_verified=user.email_verified,
    )
