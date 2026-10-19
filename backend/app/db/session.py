"""Engine and session configuration (SQLAlchemy).

Foundation for the modular monolith database layer
(`docs/09_Migration_Analysis.md` §4). PostgreSQL (Supabase) is the
documented production database (`docs/05_Database_Design.md` §3); the
default local URL is a gitignored SQLite file for development only.
"""

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    database_url = settings.sqlalchemy_database_url
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=not database_url.startswith("sqlite"),
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request):
    """FastAPI dependency yielding a database session for a request."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session
