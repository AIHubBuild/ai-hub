"""Follow-up question node.

Ported from the legacy `nodes/ask_questions.py` (KEEP). The per-category
questions and the generic fallback are preserved; a targeted question
was added for network connectivity issues because the answer changes
the troubleshooting path.
"""

from typing import Any, Callable


def ask_questions(state: dict) -> dict:
    issue_type = state.get("issue_type", "")

    if issue_type == "password_reset":
        question = (
            "Have you tried resetting your password in the company portal, "
            "and what message appears when you try?"
        )
    elif issue_type == "vpn_issue":
        question = (
            "What happens when you connect: do you get an error code, a "
            "timeout, or does it connect but no resources load?"
        )
    elif issue_type == "email_issue":
        question = (
            "Can you send and receive email, and is there an exact error "
            "message in Outlook or on the web?"
        )
    elif issue_type == "network_issue":
        question = (
            "Is the device unable to connect to Wi-Fi at all, or is it "
            "connected but web pages do not load?"
        )
    elif issue_type == "hardware_issue":
        question = (
            "What is the exact stop code or error message, when did it "
            "start, and did anything change just before it, such as a "
            "Windows update or new device?"
        )
    elif issue_type == "access_issue":
        question = (
            "Which system or resource are you trying to access, and what "
            "exactly happens when you try?"
        )
    else:
        question = (
            "What exactly happens, what is the exact error text, and when "
            "did it start?"
        )

    return {"follow_up_question": question}
