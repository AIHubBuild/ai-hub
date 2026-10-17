"""LangGraph state for the IT Support Copilot workflow.

Ported from the standalone Copilot's `state.py` (KEEP, `docs/09_Migration_Analysis.md`
§3.2). Field names and semantics are preserved unchanged.
"""

from typing import List

from typing_extensions import TypedDict


class ITSupportState(TypedDict, total=False):
    user_issue: str
    conversation_history: str
    issue_type: str
    knowledge_base: str
    follow_up_question: str
    diagnostic_context: str
    troubleshooting_steps: List[str]
    resolution: str
    root_cause_summary: str
    escalation_needed: bool


def empty_state() -> ITSupportState:
    """Initial state matching the legacy Streamlit entry point."""
    return ITSupportState(
        user_issue="",
        conversation_history="",
        issue_type="",
        knowledge_base="",
        follow_up_question="",
        diagnostic_context="",
        troubleshooting_steps=[],
        resolution="",
        root_cause_summary="",
        escalation_needed=False,
    )
