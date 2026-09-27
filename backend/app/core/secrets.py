"""Secret access helpers.

Centralizes retrieval of service secrets so the rest of the codebase
never depends on how a secret is sourced (environment today; a secret
manager per `docs/06_AWS_Cloud_Architecture.md` in production).
"""

from app.core.config import Settings


class SecretError(RuntimeError):
    """Raised when a required secret is not configured."""


def require_secret(settings: Settings, name: str) -> str:
    """Return the configured value for `name`, failing loudly if unset.

    Names follow the environment variable names in `.env.example`
    (e.g. ``supabase_jwt_secret``).
    """
    value = getattr(settings, name, "")
    if not value:
        raise SecretError(
            f"Required secret '{name}' is not configured. "
            f"Set it in the environment or .env file — never commit real values."
        )
    return value
