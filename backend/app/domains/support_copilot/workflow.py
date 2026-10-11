"""LangGraph workflow for the Support Copilot domain.

Ported from the standalone Copilot's `workflow.py` (KEEP,
`docs/09_Migration_Analysis.md` §3.2): the node graph, routing, and edge
structure are preserved exactly:

    classify_issue ──(security_issue)──▶ escalate ──▶ END
            │
            └──────▶ retrieve_knowledge ──▶ ask_questions ──▶ troubleshoot ──▶ END

Because AI Hub's session service also calls the troubleshoot and
root-cause steps directly for follow-up turns (mirroring the legacy
Streamlit orchestration), each step is additionally exposed as a
standalone state→state workflow so every LLM invocation goes through
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
from app.domains.support_copilot.state import ITSupportState

SUPPORT_WORKFLOW_ID = "support_copilot/support_workflow"
TROUBLESHOOT_STEP_ID = "support_copilot/troubleshoot_step"
ROOT_CAUSE_STEP_ID = "support_copilot/root_cause_step"


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        ...


def build_support_workflow(client: ChatClient, prompts: PromptRegistry):
    """Assemble and compile the ported support graph."""
    graph = StateGraph(ITSupportState)

    graph.add_node("classify_issue", make_classify_issue_node(client, prompts))
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("ask_questions", ask_questions)
    graph.add_node("troubleshoot", make_troubleshoot_node(client, prompts))
    graph.add_node("escalate", escalate)

    graph.set_entry_point("classify_issue")

    def route_issue(state: ITSupportState) -> str:
        if state.get("issue_type") == "security_issue":
            return "escalate"
        return "retrieve_knowledge"

    graph.add_conditional_edges(
        "classify_issue",
        route_issue,
        {"retrieve_knowledge": "retrieve_knowledge", "escalate": "escalate"},
    )
    graph.add_edge("retrieve_knowledge", "ask_questions")
    graph.add_edge("ask_questions", "troubleshoot")
    graph.add_edge("troubleshoot", END)
    graph.add_edge("escalate", END)

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
