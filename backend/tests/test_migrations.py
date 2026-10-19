"""Tests for the Alembic migration foundation."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]

POSTGRES_TEST_URL = (
    "postgresql+psycopg://test_user:test_password@"
    "db.example.com:5432/postgres?sslmode=require"
)


def make_alembic_config(tmp_path, db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def table_names(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def test_migration_graph_has_single_head_at_0010(tmp_path):
    cfg = make_alembic_config(
        tmp_path, f"sqlite:///{tmp_path / 'head.db'}"
    )

    script = ScriptDirectory.from_config(cfg)

    assert script.get_heads() == ["0010"]


def test_alembic_rejects_sqlite_in_production(tmp_path, monkeypatch):
    import app.core.config as config_module
    from app.core.config import DatabaseConfigError

    db_url = f"sqlite:///{tmp_path / 'production.db'}"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AI_DEPLOYMENT", "true")
    monkeypatch.setenv("DATABASE_URL", db_url)
    config_module.get_settings.cache_clear()
    cfg = make_alembic_config(tmp_path, db_url)

    try:
        with pytest.raises(DatabaseConfigError):
            command.upgrade(cfg, "head", sql=True)
    finally:
        config_module.get_settings.cache_clear()


def test_postgresql_offline_upgrade_compiles(tmp_path, capsys):
    cfg = make_alembic_config(tmp_path, POSTGRES_TEST_URL)

    command.upgrade(cfg, "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE ai_run_records" in sql
    assert "CREATE TABLE admin_users" in sql
    assert "CREATE TABLE admin_audit_events" in sql
    assert "CREATE TABLE admin_incidents" in sql
    assert "CREATE TABLE user_entitlements" in sql
    assert "CREATE TABLE user_profiles" in sql
    assert "user_profiles_select_own" in sql
    assert "user_profiles_insert_own" not in sql
    assert "user_profiles_update_own" not in sql
    assert "REVOKE INSERT, UPDATE, DELETE" in sql
    assert "GRANT SELECT ON TABLE user_profiles" in sql
    assert "REVOKE ALL ON TABLE user_profiles FROM authenticated" in sql
    assert "GRANT INSERT, UPDATE" not in sql
    assert "ALTER TABLE admin_audit_events ADD COLUMN actor_user_id UUID" in sql
    assert "ALTER TABLE admin_audit_events ALTER COLUMN admin_user_id DROP NOT NULL" in sql
    assert "CREATE INDEX ix_ai_run_records_domain_created_at" in sql
    assert "CREATE INDEX ix_admin_incidents_status" in sql


def test_postgresql_offline_upgrade_accepts_percent_encoded_password(
    tmp_path, monkeypatch, capsys
):
    import app.core.config as config_module

    encoded_url = (
        "postgresql+psycopg://test_user:test%24password@"
        "db.example.com:5432/postgres?sslmode=require"
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_DEPLOYMENT", "false")
    monkeypatch.setenv("DATABASE_URL", encoded_url)
    config_module.get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    try:
        command.upgrade(cfg, "head", sql=True)
    finally:
        config_module.get_settings.cache_clear()

    sql = capsys.readouterr().out
    assert "CREATE TABLE ai_run_records" in sql
    assert "CREATE TABLE admin_incidents" in sql
    assert "CREATE TABLE user_entitlements" in sql
    assert "CREATE TABLE user_profiles" in sql


def test_postgresql_offline_downgrade_compiles(tmp_path, capsys):
    cfg = make_alembic_config(tmp_path, POSTGRES_TEST_URL)

    command.downgrade(cfg, "0010:0003", sql=True)

    sql = capsys.readouterr().out
    assert "DROP TABLE user_profiles" in sql
    assert "DROP TABLE user_entitlements" in sql
    assert "DROP TABLE admin_incidents" in sql
    assert "DROP COLUMN actor_is_admin" in sql
    assert "DROP COLUMN actor_user_id" in sql
    assert "ALTER COLUMN admin_user_id SET NOT NULL" in sql
    assert "DROP TABLE admin_users" in sql


def test_upgrade_head_creates_run_records_table(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "head")

    tables = table_names(db_url)
    assert "ai_run_records" in tables
    assert "alembic_version" in tables


def test_downgrade_base_drops_run_records_table(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg = make_alembic_config(tmp_path, db_url)
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")

    tables = table_names(db_url)
    assert "ai_run_records" not in tables


def test_migration_supports_store_usage(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg = make_alembic_config(tmp_path, db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    from sqlalchemy.orm import sessionmaker

    from app.ai_core import RunRecord, SQLAlchemyRunRecordStore

    store = SQLAlchemyRunRecordStore(
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    )
    record = RunRecord(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        domain="resume_ats",
        workflow_id="resume_ats/ats_pipeline",
        input_state={"resume_text": "abc"},
    )
    store.save(record)

    assert store.get(record.run_id) == record


def test_admin_migration_is_additive_and_reversible(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'admin-migrate.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "head")
    upgraded = table_names(db_url)

    assert "admin_users" in upgraded
    assert "user_account_status" in upgraded
    assert "admin_audit_events" in upgraded
    assert "ai_run_records" in upgraded

    command.downgrade(cfg, "0003")
    downgraded = table_names(db_url)

    assert "admin_users" not in downgraded
    assert "user_account_status" not in downgraded
    assert "admin_audit_events" not in downgraded
    assert "user_profiles" not in downgraded
    assert "ai_run_records" in downgraded


def test_ai_usage_indexes_are_additive_and_reversible(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'usage-indexes.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.connect() as connection:
        indexes = {
            item["name"]
            for item in inspect(connection).get_indexes("ai_run_records")
        }
        columns = {
            item["name"]
            for item in inspect(connection).get_columns("ai_run_records")
        }

    assert "error_category" in columns
    assert "ix_ai_run_records_user_id" in indexes
    assert "ix_ai_run_records_created_at" in indexes
    assert "ix_ai_run_records_domain_created_at" in indexes
    assert "ix_ai_run_records_status_created_at" in indexes
    assert "ix_ai_run_records_error_category_created_at" in indexes
    assert "ix_ai_run_records_user_id_created_at" in indexes

    command.downgrade(cfg, "0005")
    engine = create_engine(db_url)
    with engine.connect() as connection:
        indexes = {
            item["name"]
            for item in inspect(connection).get_indexes("ai_run_records")
        }
        columns = {
            item["name"]
            for item in inspect(connection).get_columns("ai_run_records")
        }

    assert "error_category" not in columns
    assert indexes == {"ix_ai_run_records_user_id"}


def test_incident_and_entitlement_migrations_are_additive_and_reversible(
    tmp_path,
):
    db_url = f"sqlite:///{tmp_path / 'incidents-entitlements.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "head")
    upgraded = table_names(db_url)

    assert "admin_incidents" in upgraded
    assert "user_entitlements" in upgraded
    assert "admin_users" in upgraded

    command.downgrade(cfg, "0006")
    downgraded = table_names(db_url)

    assert "admin_incidents" not in downgraded
    assert "user_entitlements" not in downgraded
    assert "admin_users" in downgraded


def test_user_profile_migration_is_additive_and_reversible(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'user-profiles.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.connect() as connection:
        assert "user_profiles" in set(
            inspect(connection).get_table_names()
        )
        columns = {
            item["name"]
            for item in inspect(connection).get_columns("user_profiles")
        }
        indexes = {
            item["name"]
            for item in inspect(connection).get_indexes("user_profiles")
        }

    assert {
        "user_id",
        "full_name",
        "phone",
        "country_code",
        "city",
        "career_goal",
        "marketing_consent",
        "terms_accepted_at",
        "privacy_accepted_at",
    } <= columns
    assert "ix_user_profiles_updated_at" in indexes

    command.downgrade(cfg, "0008")
    tables = table_names(db_url)

    assert "user_profiles" not in tables
    assert "admin_users" in tables


def test_new_admin_migrations_preserve_existing_records(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'admin-data-preservation.db'}"
    cfg = make_alembic_config(tmp_path, db_url)

    command.upgrade(cfg, "0006")
    engine = create_engine(db_url)
    from sqlalchemy.orm import sessionmaker

    from app.models.admin import AdminAuditEvent, AdminIncident, AdminUser, UserEntitlement
    from app.models.ai_run_record import AIRunRecord

    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    now = datetime.now(timezone.utc)
    run_id = "1" * 32
    admin_id = "2" * 32
    user_id = "3" * 32
    event_id = "4" * 32
    incident_id = "5" * 32

    with session_factory() as session:
        session.add(
            AIRunRecord(
                run_id=run_id,
                user_id=user_id,
                domain="resume_ats",
                workflow_id="resume_ats/ats_pipeline",
                model="gpt-test",
                input_state={"resume_text": "private"},
                output_state={"result": "ok"},
                status="success",
                latency_ms=42,
                created_at=now,
            )
        )
        session.add(AdminUser(user_id=admin_id))
        session.add(
            AdminAuditEvent(
                event_id=event_id,
                actor_user_id=admin_id,
                admin_user_id=admin_id,
                actor_is_admin=True,
                action="test.existing",
                target_type="test",
                success=True,
            )
        )
        session.commit()

    command.upgrade(cfg, "head")

    with session_factory() as session:
        session.add(
            AdminIncident(
                incident_id=incident_id,
                title="Test incident",
                description="Operational test",
                category="platform",
                priority="medium",
                status="open",
                created_by=admin_id,
            )
        )
        session.add(
            UserEntitlement(
                user_id=user_id,
                tier="pro",
                source="manual",
                granted_by=admin_id,
                reason="test grant",
            )
        )
        session.commit()

    command.downgrade(cfg, "0006")
    tables = table_names(db_url)
    assert "admin_incidents" not in tables
    assert "user_entitlements" not in tables
    assert "user_profiles" not in tables

    with session_factory() as session:
        preserved_run = session.get(AIRunRecord, run_id)
        preserved_event = session.get(AdminAuditEvent, event_id)
        assert preserved_run is not None
        assert preserved_run.latency_ms == 42
        assert preserved_run.error_category is None
        assert preserved_event is not None
        assert preserved_event.action == "test.existing"

    command.upgrade(cfg, "head")
    with session_factory() as session:
        assert session.get(AIRunRecord, run_id) is not None
        assert session.get(AdminAuditEvent, event_id) is not None
