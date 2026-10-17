"""Escalation node.

Ported from the legacy `nodes/escalate.py` (REFACTOR): the critical-issue
list and message are preserved; the legacy `resolution +=` assumption is
guarded so escalation works even when no prior resolution text exists
(the direct-escalation path for a first security/hardware message).
"""

from typing import Any, Callable

CRITICAL_ISSUES = ["hardware_issue", "security_issue"]


def escalate(state: dict) -> dict:
    issue_type = state.get("issue_type", "")
    user_issue = state.get("user_issue", "")

    if issue_type in CRITICAL_ISSUES:
        escalation_message = (
            "This issue meets the escalation criteria. An escalation "
            f"request was recorded for: {user_issue}. No human engineer "
            "has accepted the ticket yet."
        )
        resolution = state.get("resolution") or ""
        return {
            "escalation_needed": True,
            "resolution": resolution + "\n\nESCALATION NOTICE:\n" + escalation_message,
        }

    return {"escalation_needed": False}
