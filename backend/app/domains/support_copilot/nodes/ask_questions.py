"""Follow-up question node.

Ported from the legacy `nodes/ask_questions.py` (KEEP). The per-category
questions and the generic fallback are preserved exactly.
"""

from typing import Any, Callable


def ask_questions(state: dict) -> dict:
    issue_type = state.get("issue_type", "")

    if issue_type == "password_reset":
        question = (
            "Have you tried resetting your password using the company portal?"
        )
    elif issue_type == "vpn_issue":
        question = "Are you receiving any VPN error messages?"
    elif issue_type == "email_issue":
        question = "Can you send or receive emails?"
    else:
        question = "Can you provide more details about the issue?"

    return {"follow_up_question": question}
