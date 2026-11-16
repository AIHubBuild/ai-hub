"""protect backend-only tables from Supabase Data API access

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-19

The backend connects directly as the PostgreSQL owner role (``postgres``),
which has ``BYPASSRLS``. Supabase's default privileges, however, granted
``anon`` and ``authenticated`` full table access to every table created
in ``public``. That exposed backend-only data through the Supabase Data
API even though the FastAPI endpoints required authentication.

This migration:

- enables RLS with no policies on backend-only tables, so the anon and
  authenticated roles are denied even if a future grant is accidentally
  added;
- revokes all existing table privileges from PUBLIC, ``anon``, and
  ``authenticated`` on those tables;
- revokes default table/sequence privileges for objects created by the
  migration role in ``public`` so new backend tables are not exposed.

It deliberately does not touch ``user_profiles``. That table already has
RLS and the self-only SELECT policy required by the profile API.
``service_role`` and the backend owner role keep their access. Existing
backend SQLAlchemy access is unaffected because the owner role bypasses
RLS.

Downgrade is intentionally a no-op: restoring the exposed grants would
reintroduce the vulnerability. A database restore is the rollback path.
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Every backend-only table in public. user_profiles is intentionally
# excluded because it has its own RLS SELECT policy and authenticated
# read access for the profile API.
BACKEND_TABLES = (
    "admin_audit_events",
    "admin_incidents",
    "admin_users",
    "ai_run_records",
    "alembic_version",
    "ats_analyses",
    "resumes",
    "support_sessions",
    "support_tickets",
    "user_account_status",
    "user_entitlements",
)

_API_ROLES = ("anon", "authenticated")


def _revoke_table_privileges() -> None:
    for table in BACKEND_TABLES:
        op.execute(
            f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'
        )
        op.execute(
            f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC'
        )

    statements: list[str] = []
    for role in _API_ROLES:
        statements.append(
            f"IF EXISTS (SELECT 1 FROM pg_roles "
            f"WHERE rolname = '{role}') THEN"
        )
        for table in BACKEND_TABLES:
            statements.append(
                f"EXECUTE 'REVOKE ALL ON TABLE \"{table}\" FROM {role}';"
            )
        statements.append("END IF;")

    op.execute("DO $$ BEGIN " + " ".join(statements) + " END $$")


def _revoke_default_privileges() -> None:
    # These statements apply to objects created by the role running the
    # migration. Future Alembic migrations run as the same PostgreSQL
    # owner role, so newly created tables and sequences inherit this
    # deny-by-default posture.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM PUBLIC"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM PUBLIC"
    )

    statements: list[str] = []
    for role in _API_ROLES:
        statements.append(
            f"IF EXISTS (SELECT 1 FROM pg_roles "
            f"WHERE rolname = '{role}') THEN"
        )
        statements.append(
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE ALL ON TABLES FROM {role}';"
        )
        statements.append(
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE ALL ON SEQUENCES FROM {role}';"
        )
        statements.append("END IF;")

    op.execute("DO $$ BEGIN " + " ".join(statements) + " END $$")


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    _revoke_table_privileges()
    _revoke_default_privileges()


def downgrade() -> None:
    # Never restore anon/authenticated access automatically. The safe
    # rollback is restoring the pre-migration database backup.
    pass
