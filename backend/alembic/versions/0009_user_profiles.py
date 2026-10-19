"""create user profiles with Supabase RLS

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19

The profile is keyed by the Supabase Auth user UUID. Authentication
identity, email, and password remain owned by Supabase Auth. RLS is
enabled only on PostgreSQL and a read-only self policy is created only
when the Supabase ``auth.uid()`` function and roles are present. Direct
writes are denied so profile mutations must pass through FastAPI
validation. The same migration remains runnable on local SQLite and
disposable PostgreSQL.
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("career_goal", sa.String(length=200), nullable=True),
        sa.Column(
            "marketing_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "terms_accepted_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("terms_version", sa.String(length=32), nullable=False),
        sa.Column(
            "privacy_accepted_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("privacy_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_user_profiles_updated_at",
        "user_profiles",
        ["updated_at"],
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY"
        )
        op.execute("REVOKE ALL ON TABLE user_profiles FROM PUBLIC")
        op.execute(
            """
            DO $$
            BEGIN
                IF to_regprocedure('auth.uid()') IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM pg_roles
                       WHERE rolname = 'authenticated'
                   )
                THEN
                    EXECUTE 'CREATE POLICY user_profiles_select_own ON user_profiles FOR SELECT TO authenticated USING (auth.uid() = user_id)';
                    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON TABLE user_profiles FROM authenticated';
                    EXECUTE 'GRANT SELECT ON TABLE user_profiles TO authenticated';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'anon'
                ) THEN
                    EXECUTE 'REVOKE ALL ON TABLE user_profiles FROM anon';
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.drop_index(
        "ix_user_profiles_updated_at", table_name="user_profiles"
    )
    op.drop_table("user_profiles")
