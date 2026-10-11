"""create resumes and ats_analyses

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11

Resume ATS domain tables (`docs/09_Migration_Analysis.md` §5 Phase 2
item 11; `docs/05_Database_Design.md` §7.2 RESUMES/RESUME_VERSIONS):
uploaded resumes with extracted text, and one record per ATS analysis
run linked to the ai_core run record. UUID primary keys per
`docs/05_Database_Design.md` §4.2. Dialect-portable types (Uuid, JSON)
so the migration applies to SQLite and PostgreSQL alike.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])

    op.create_table(
        "ats_analyses",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("resume_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("ats_score", sa.Integer(), nullable=False),
        sa.Column("matching_keywords", sa.JSON(), nullable=False),
        sa.Column("missing_keywords", sa.JSON(), nullable=False),
        sa.Column("improvement_suggestions", sa.Text(), nullable=True),
        sa.Column("tailored_resume", sa.Text(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_ats_analyses_resume_id", "ats_analyses", ["resume_id"])
    op.create_index("ix_ats_analyses_run_id", "ats_analyses", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_ats_analyses_run_id", table_name="ats_analyses")
    op.drop_index("ix_ats_analyses_resume_id", table_name="ats_analyses")
    op.drop_table("ats_analyses")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.drop_table("resumes")
