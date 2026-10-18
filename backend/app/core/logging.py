"""Application logging configuration.

Phase 1 slice: structured, level-configurable logging for the modular
monolith (`docs/09_Migration_Analysis.md` §5 Phase 1). Domains and
services use the standard ``logging`` module; no third-party dependency.

All output passes through ``RedactingFormatter`` so accidental secrets in
log messages or tracebacks are masked. Request logging itself is
metadata-only.
"""

import logging

from app.core.config import Settings
from app.core.redaction import RedactingFormatter

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

_configured = False

_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _harden_uvicorn_handlers() -> None:
    """Apply the redacting formatter to Uvicorn's own handlers.

    Uvicorn installs handlers on its own loggers with ``propagate=False``
    for access logs, so those records would otherwise bypass the root
    handler. This only replaces formatters; it does not add handlers, so
    log entries are not duplicated.
    """
    seen: set[int] = set()
    for name in _UVICORN_LOGGER_NAMES:
        for handler in logging.getLogger(name).handlers:
            if id(handler) in seen:
                continue
            seen.add(id(handler))
            existing = handler.formatter
            fmt = getattr(existing, "_fmt", None) or LOG_FORMAT
            handler.setFormatter(RedactingFormatter(fmt))


def configure_logging(settings: Settings) -> None:
    """Configure the root logger from application settings.

    The root handler is installed once per process. Subsequent calls
    (for example, when tests create additional app instances) only adjust
    the level, so existing handlers such as pytest's caplog are preserved.
    """
    global _configured

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter(LOG_FORMAT))
        logging.basicConfig(level=level, handlers=[handler], force=True)
        _configured = True

    logging.getLogger().setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _harden_uvicorn_handlers()
    # HTTP client libraries log request URLs at INFO, which can include
    # query strings. Keep their routine request logs quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
