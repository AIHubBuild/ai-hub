"""Support Copilot workflow nodes.

Ported from the standalone Copilot's `nodes/` package
(`docs/09_Migration_Analysis.md` §3.2 KEEP/REFACTOR). Logic and prompts
are preserved; LLM access goes through the shared ai_core client seam,
and classification output is validated against the allowed categories.
"""

from app.domains.support_copilot.nodes.ask_questions import (
    ask_questions as ask_questions,
)
from app.domains.support_copilot.nodes.classify_issue import (
    make_classify_issue_node as make_classify_issue_node,
)
from app.domains.support_copilot.nodes.escalate import escalate as escalate
from app.domains.support_copilot.nodes.retrieve_knowledge import (
    retrieve_knowledge as retrieve_knowledge,
)
from app.domains.support_copilot.nodes.root_cause import (
    make_root_cause_node as make_root_cause_node,
)
from app.domains.support_copilot.nodes.troubleshoot import (
    make_troubleshoot_node as make_troubleshoot_node,
)

__all__ = [
    "ask_questions",
    "escalate",
    "make_classify_issue_node",
    "make_root_cause_node",
    "make_troubleshoot_node",
    "retrieve_knowledge",
]
