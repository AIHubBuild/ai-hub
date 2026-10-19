"""reduce user_profiles privileges to SELECT only

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19

Migration 0009 revoked INSERT, UPDATE, and DELETE but Supabase's default
privileges can still leave REFERENCES, TRIGGER, and TRUNCATE on the
authenticated role. This corrective migration removes every direct table
privilege and grants back only SELECT. RLS continues to restrict rows to
the authenticated user.
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'
            ) THEN
                EXECUTE 'REVOKE ALL ON TABLE user_profiles FROM authenticated';
                EXECUTE 'GRANT SELECT ON TABLE user_profiles TO authenticated';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Intentionally do not restore unsafe write/DDL privileges. The
    # preceding migration drops the table when downgrading below 0009.
    pass
