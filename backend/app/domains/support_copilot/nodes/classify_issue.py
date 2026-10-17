"""Issue classification node.

Ported from the legacy `nodes/classify_issue.py`. The prompt (now a
versioned registry template) and category list are preserved. The LLM
response is validated against the allowed categories plus the reserved
``not_an_it_issue`` output for non-IT messages; unexpected output falls
back to "general" (which the knowledge loader already handled via its
default branch) instead of silently breaking routing.
"""

from typing import Any, Callable, Protocol

from app.ai_core.prompts import PromptRegistry
from app.domains.support_copilot.prompts import (
    CLASSIFIER_CATEGORIES,
    NOT_AN_IT_ISSUE,
)


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        ...


_ALLOWED_OUTPUTS = set(CLASSIFIER_CATEGORIES) | {NOT_AN_IT_ISSUE}


def make_classify_issue_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[dict], dict]:
    def node(state: dict) -> dict:
        template = prompts.get("support_copilot/classify_issue")
        user = template.user_template.format(
            user_issue=state.get("user_issue", "")
        )
        response = client.complete(system=template.system, user=user)
        issue_type = str(response).strip()
        if issue_type not in _ALLOWED_OUTPUTS:
            issue_type = "general"
        return {"issue_type": issue_type}

    return node
