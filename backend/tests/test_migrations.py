"""Tests for the Alembic migration foundation."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]


def make_alembic_config(tmp_path, db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def table_names(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


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
