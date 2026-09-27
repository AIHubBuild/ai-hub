"""Prompt registry.

Versioned prompt assets shared by every AI domain (`docs/09_Migration_Analysis.md`
§3.3). Versions are immutable once registered, so run records and the
future evaluation layer can reference the exact prompt version used in a
run (§3.4.4).
"""

from pydantic import BaseModel


class PromptNotFoundError(KeyError):
    """No prompt is registered under the requested id (and version)."""


class PromptTemplate(BaseModel):
    """A versioned prompt asset.

    ``user_template`` uses ``str.format`` placeholders populated by the
    domain at runtime (e.g. ``{resume_text}``, ``{job_description}``).
    """

    prompt_id: str
    version: int = 1
    system: str
    user_template: str


class PromptRegistry:
    """Stores prompt templates keyed by ``prompt_id`` + ``version``."""

    def __init__(self):
        self._prompts: dict[tuple[str, int], PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        key = (template.prompt_id, template.version)
        if key in self._prompts:
            raise ValueError(
                f"Prompt '{template.prompt_id}' version {template.version} "
                f"is already registered."
            )
        self._prompts[key] = template

    def get(self, prompt_id: str, version: int | None = None) -> PromptTemplate:
        if version is None:
            versions = self.list_versions(prompt_id)
            if not versions:
                raise PromptNotFoundError(
                    f"No prompt registered for prompt id '{prompt_id}'."
                )
            version = versions[-1]
        try:
            return self._prompts[(prompt_id, version)]
        except KeyError:
            raise PromptNotFoundError(
                f"No prompt registered for prompt id '{prompt_id}' "
                f"version {version}."
            ) from None

    def list_versions(self, prompt_id: str) -> list[int]:
        return sorted(
            version for (pid, version) in self._prompts if pid == prompt_id
        )
