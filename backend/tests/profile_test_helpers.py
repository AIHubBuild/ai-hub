"""Helpers for seeding complete profiles in API tests."""

from datetime import datetime, timezone

from app.models.profile import UserProfile


def seed_complete_profile(app, *user_ids: str, full_name: str = "Test User") -> None:
    now = datetime.now(timezone.utc)
    with app.state.session_factory() as session:
        for user_id in user_ids:
            if session.get(UserProfile, user_id) is None:
                session.add(
                    UserProfile(
                        user_id=user_id,
                        full_name=full_name,
                        marketing_consent=False,
                        terms_accepted_at=now,
                        terms_version="test",
                        privacy_accepted_at=now,
                        privacy_version="test",
                    )
                )
        session.commit()
