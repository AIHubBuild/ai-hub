"""Alembic environment.

Resolves the database URL as follows: an explicit ``sqlalchemy.url``
set by callers (e.g. tests) wins; otherwise the application settings
default applies, which honors ``DATABASE_URL`` whether exported or
loaded from ``.env``. Targets the metadata of all SQLAlchemy models
in ``app/models``.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import (
    get_settings,
    normalize_database_url,
    validate_database_config,
)
from app.models import Base

config = context.config

if config.config_file_name is not None:
    # Do not disable application loggers when Alembic is invoked
    # in-process (for example from tests or a management command).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

settings = get_settings()
configured_url = config.get_main_option("sqlalchemy.url")
if configured_url:
    # Tests and explicit invocations may set the URL directly. Normalize
    # bare PostgreSQL URLs and apply the same environment safety check.
    normalized_url = normalize_database_url(configured_url)
    validated_settings = settings.model_copy(
        update={"database_url": normalized_url}
    )
    validate_database_config(validated_settings)
    config.set_main_option("sqlalchemy.url", normalized_url)
else:
    validate_database_config(settings)
    config.set_main_option(
        "sqlalchemy.url", settings.sqlalchemy_database_url
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
