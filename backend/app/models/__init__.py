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
from app.models.resume import AtsAnalysisRecord, Resume  # noqa: E402,F401
from app.models.support import SupportSession, SupportTicket  # noqa: E402,F401

__all__ = [
    "Base",
    "AIRunRecord",
    "Resume",
    "AtsAnalysisRecord",
    "SupportSession",
    "SupportTicket",
]
