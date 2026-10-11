"""Resume ATS domain database models.

`resumes` stores uploaded resumes (metadata + extracted text; object
storage arrives with Supabase in a later phase — `docs/09` §5 Phase 2
item 11). `ats_analyses` stores one record per ATS analysis run and
links to the ai_core run record. UUID primary keys per
`docs/05_Database_Design.md` §4.2.

Note: authentication is not implemented yet, so `user_id` currently
always holds the shared anonymous user id assigned by the domain
service. When Supabase Auth lands, these rows gain real user identity
and per-user isolation.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class AtsAnalysisRecord(Base):
    __tablename__ = "ats_analyses"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    resume_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    ats_score: Mapped[int] = mapped_column(Integer, nullable=False)
    matching_keywords: Mapped[list] = mapped_column(JSON, nullable=False)
    missing_keywords: Mapped[list] = mapped_column(JSON, nullable=False)
    improvement_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    tailored_resume: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
