"""Knowledge retrieval node.

Ported from the legacy `nodes/retrieve_knowledge.py` (KEEP).
"""

from typing import Any, Callable

from app.domains.support_copilot.knowledge_loader import load_knowledge


def retrieve_knowledge(state: dict) -> dict:
    issue_type = state.get("issue_type", "")
    return {"knowledge_base": load_knowledge(issue_type)}
