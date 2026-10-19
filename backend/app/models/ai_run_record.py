"""Persistent AI run record.

The database representation of ``ai_core`` run records — the shared
"run records" table from `docs/09_Migration_Analysis.md` §5 Phase 1
item 8, persisted from day one as the substrate for product history and
the future evaluation layer (§3.4.1). UUID primary keys follow
`docs/05_Database_Design.md` §4.2.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# Values match ai_core.run_records.RunStatus ("success" | "error").
# Kept as a plain literal so models never import from ai_core.
_RUN_STATUS_DEFAULT = "success"


class AIRunRecord(Base):
    __tablename__ = "ai_run_records"

    run_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    input_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=_RUN_STATUS_DEFAULT
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
