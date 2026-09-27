"""SQLAlchemy models package.

Schema metadata lives here (`docs/09_Migration_Analysis.md` §4:
app/models/ — SQLAlchemy/Pydantic models). All tables derive from
``Base`` so Alembic migrations can autogenerate against the full
metadata.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.ai_run_record import AIRunRecord  # noqa: E402,F401

__all__ = ["Base", "AIRunRecord"]
