"""LangGraph workflow for the Support Copilot domain.

Ported from the standalone Copilot's `workflow.py` (KEEP,
`docs/09_Migration_Analysis.md` §3.2): the node graph, routing, and edge
structure are preserved exactly:

    classify_issue ──(security_issue)──▶ escalate ──▶ END
            │
            └──────▶ retrieve_knowledge ──▶ ask_questions ──▶ END

The first turn diagnoses before prescribing: it classifies the issue,
retrieves knowledge, and asks one focused question. The service calls
the standalone troubleshoot step on later turns, using the user's answer
to choose the next action. Every LLM invocation still goes through
ai_core's runner and is captured as a run record.
"""

from typing import Any, Callable, Protocol

from langgraph.graph import END, StateGraph

from app.ai_core.prompts import PromptRegistry
from app.domains.support_copilot.nodes import (
    ask_questions,
    escalate,
    make_classify_issue_node,
    make_root_cause_node,
    make_troubleshoot_node,
    retrieve_knowledge,
)
from app.domains.support_copilot.prompts import NOT_AN_IT_ISSUE
from app.domains.support_copilot.state import ITSupportState

SUPPORT_WORKFLOW_ID = "support_copilot/support_workflow"
TROUBLESHOOT_STEP_ID = "support_copilot/troubleshoot_step"
ROOT_CAUSE_STEP_ID = "support_copilot/root_cause_step"

NOT_IT_CLARIFICATION_TEXT = (
    "That doesn't sound like an IT issue. I'm the IT Support Copilot. "
    "I can help with things like VPN problems, password resets, network "
    "connectivity, or device trouble. Is there an IT issue I can help "
    "you with?"
)


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        ...


def clarify_non_it(state: ITSupportState) -> dict:
    """Deterministic clarification for messages that are not IT issues."""
    return {
        "resolution": NOT_IT_CLARIFICATION_TEXT,
        "follow_up_question": "",
    }


def build_support_workflow(client: ChatClient, prompts: PromptRegistry):
    """Assemble and compile the ported support graph."""
    graph = StateGraph(ITSupportState)

    graph.add_node("classify_issue", make_classify_issue_node(client, prompts))
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("ask_questions", ask_questions)
    graph.add_node("escalate", escalate)
    graph.add_node("clarify", clarify_non_it)

    graph.set_entry_point("classify_issue")

    def route_issue(state: ITSupportState) -> str:
        if state.get("issue_type") == "security_issue":
            return "escalate"
        if state.get("issue_type") == NOT_AN_IT_ISSUE:
            return "clarify"
        return "retrieve_knowledge"

    graph.add_conditional_edges(
        "classify_issue",
        route_issue,
        {
            "retrieve_knowledge": "retrieve_knowledge",
            "escalate": "escalate",
            "clarify": "clarify",
        },
    )
    graph.add_edge("retrieve_knowledge", "ask_questions")
    graph.add_edge("ask_questions", END)
    graph.add_edge("escalate", END)
    graph.add_edge("clarify", END)

    return graph.compile()


def make_troubleshoot_step(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[dict], dict]:
    """Standalone troubleshoot step (follow-up turns)."""
    return make_troubleshoot_node(client, prompts)


def make_root_cause_step(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[dict], dict]:
    """Standalone root-cause step (ticket resolution)."""
    return make_root_cause_node(client, prompts)
