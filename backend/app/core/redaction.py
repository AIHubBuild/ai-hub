"""Log redaction helpers.

Defense in depth for application logs: credentials, bearer tokens, API
keys, JWTs, and URLs with embedded passwords are replaced before output.
Request logging is intentionally metadata-only (method, path, status,
duration, request id) and never records bodies, query strings, headers,
prompts, or model output.
"""

from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

# Secret-bearing key names, optionally prefixed (OPENAI_API_KEY,
# openai_api_key, SENTRY_DSN, SUPABASE_SERVICE_ROLE_KEY, ...). Matching is
# case-insensitive and allows an optional common suffix such as _ID/_FILE.
_SECRET_NAME = (
    r"[A-Za-z0-9_.-]*"
    r"(?:"
    r"api[_-]?key|"
    r"secret[_-]?key|"
    r"private[_-]?key|"
    r"access[_-]?key|"
    r"client[_-]?secret|"
    r"service[_-]?role[_-]?key|"
    r"secret|"
    r"token|"
    r"password|"
    r"passwd|"
    r"dsn"
    r")"
    r"(?:[_-](?:id|file|path|name|value|url))?"
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization headers and bearer tokens.
    (
        re.compile(r"(?i)\b(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
        f"Bearer {REDACTED}",
    ),
    # key=value / key: value pairs for common secret names, including
    # lowercase and prefixed environment-style names.
    (
        re.compile(
            rf"(?i)\b({_SECRET_NAME})(\s*[:=]\s*)"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
        ),
        rf"\1\2{REDACTED}",
    ),
    # OpenAI-style keys.
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), REDACTED),
    # JWTs.
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
        ),
        REDACTED,
    ),
    # URLs with embedded credentials, e.g. postgresql://user:pass@host/db.
    (
        re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"),
        rf"\1{REDACTED}@",
    ),
)


def redact_text(text: str) -> str:
    """Return `text` with known secret patterns replaced.

    This is best-effort defense in depth, not a substitute for never
    passing sensitive values to log calls in the first place.
    """
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the fully rendered log record.

    Formatting first means tracebacks and interpolated arguments are also
    covered.
    """

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))
