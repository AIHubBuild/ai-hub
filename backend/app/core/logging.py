"""Application logging configuration.

Phase 1 slice: structured, level-configurable logging for the modular
monolith (`docs/09_Migration_Analysis.md` §5 Phase 1). Domains and
services use the standard ``logging`` module; no third-party dependency.
"""

import logging

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(settings: Settings) -> None:
    """Configure the root logger from application settings.

    Idempotent per process: subsequent calls only adjust the level.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
