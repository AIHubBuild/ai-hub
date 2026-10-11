"""Troubleshooting node.

Ported from the legacy `nodes/troubleshoot.py` (REFACTOR): the prompt is
a versioned registry template, the LLM call goes through the shared
client seam, and debug printing is removed. Response shaping is
preserved: the result is stored in both `troubleshooting_steps` and
`resolution`.
"""

from typing import Any, Callable, Protocol

from app.ai_core.prompts import PromptRegistry


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        ...


def make_troubleshoot_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[dict], dict]:
    def node(state: dict) -> dict:
        template = prompts.get("support_copilot/troubleshoot")
        user = template.user_template.format(
            knowledge_base=state.get("knowledge_base", ""),
            conversation_history=state.get("conversation_history", ""),
            issue_type=state.get("issue_type", ""),
            user_issue=state.get("user_issue", ""),
        )
        response = client.complete(system=template.system, user=user)
        ai_response = str(response).strip()
        return {
            "troubleshooting_steps": [ai_response],
            "resolution": ai_response,
        }

    return node
