"""Root-cause analysis node.

Ported from the legacy `nodes/root_cause.py` (KEEP): the prompt is a
versioned registry template and the LLM call goes through the shared
client seam.
"""

from typing import Any, Callable, Protocol

from app.ai_core.prompts import PromptRegistry
from app.ai_core.writing_style import normalize_writing


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        ...


def make_root_cause_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[dict], dict]:
    def node(state: dict) -> dict:
        template = prompts.get("support_copilot/root_cause")
        user = template.user_template.format(
            issue_type=state.get("issue_type", ""),
            conversation_history=state.get("conversation_history", ""),
        )
        response = client.complete(system=template.system, user=user)
        return {"root_cause_summary": normalize_writing(str(response))}

    return node
