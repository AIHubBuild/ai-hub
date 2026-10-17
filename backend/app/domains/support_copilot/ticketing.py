"""Ticket creation and status machine.

Ported from the standalone Copilot's `ticketing.py` (REFACTOR per
`docs/09_Migration_Analysis.md` §3.2): the priority/team mapping and the
keyword-driven status machine are preserved exactly. Ticket IDs are no
longer `random.randint(1000, 9999)` — persistence rows use DB-generated
UUIDs, and the user-facing `INC-` id is derived deterministically from
the UUID (see `service.display_ticket_id`).
"""

import re

# Priority / team mapping — preserved from the legacy implementation.
TICKET_DEFAULTS = {"priority": "Medium", "assigned_team": "General IT Support"}

ISSUE_TEAM_MAPPING = {
    "security_issue": {"priority": "High", "assigned_team": "Security Operations"},
    "network_issue": {"priority": "Medium", "assigned_team": "Network Team"},
    "hardware_issue": {"priority": "Medium", "assigned_team": "Hardware Support"},
    "vpn_issue": {"priority": "Medium", "assigned_team": "Remote Access Team"},
    "password_reset": {"priority": "Low", "assigned_team": "Identity Management"},
}

CONFIRMATION_KEYWORDS = [
    "confirmed",
    "confirm",
    "issue is resolved",
    "fully resolved",
    "problem solved",
    "everything works now",
]

RESOLVED_KEYWORDS = [
    "fixed",
    "resolved",
    "working now",
    "issue resolved",
    "solved",
    "vpn works",
    "it works",
    "working again",
]

# Business-impact words use word boundaries so error codes such as
# CRITICAL_PROCESS_DIED do not trigger an escalation request.
ESCALATION_WORDS = ["urgent", "critical", "outage"]

# Explicit human-handoff requests. These request escalation; they do not
# mean a human has accepted the ticket.
HUMAN_HANDOFF_PHRASES = [
    "speak to a human",
    "talk to a human",
    "speak to a person",
    "talk to a person",
    "real person",
    "human support",
    "need a human",
    "want a human",
    "escalate this",
    "escalate the ticket",
    "escalate to support",
    "raise this with support",
]

# Significant business-impact phrases.
BUSINESS_IMPACT_PHRASES = [
    "affecting everyone",
    "whole team",
    "all users",
    "company wide",
    "company-wide",
    "office is down",
    "business impact",
    "cannot work",
    "can't work",
    "unable to work",
    "is down for",
]

# Situations where the next safe step needs permissions or expertise the
# Copilot does not have.
ELEVATED_ACCESS_PHRASES = [
    "no admin",
    "don't have admin",
    "do not have admin",
    "need admin",
    "requires admin",
    "administrator rights",
    "no administrator rights",
    "can't install",
    "cannot install",
    "permission denied to install",
]

# Gratitude / conversational-closure phrases.
GRATITUDE_KEYWORDS = [
    "thank you",
    "thank u",
    "thanks",
    "cheers",
    "appreciate it",
    "appreciated",
    "much obliged",
    "great, thanks",
]

# Negations that stop a message from being read as a fix report or
# gratitude ("not fixed", "no thanks, still broken", ...).
CLOSURE_NEGATIONS = [
    "not fixed",
    "isn't fixed",
    "is not fixed",
    "haven't fixed",
    "hasn't fixed",
    "not resolved",
    "isn't resolved",
    "is not resolved",
    "still broken",
    "still not working",
    "not working",
    "doesn't work",
    "does not work",
    "no thanks",
    "no thank you",
    "still not fixed",
]

# Status values — preserved from the legacy implementation.
STATUS_OPEN = "Open"
STATUS_IN_PROGRESS = "In Progress"
STATUS_AWAITING_CONFIRMATION = "Awaiting Confirmation"
STATUS_RESOLVED = "Resolved"
STATUS_ESCALATION_REQUESTED = "Escalation Requested"
STATUS_ESCALATED = "Escalated"

# Escalation Requested means a handoff was requested but not accepted.
# Escalated is reserved for a confirmed human handoff.
# Terminal states cannot regress.
TERMINAL_STATUSES = {STATUS_RESOLVED, STATUS_ESCALATED}

_ESCALATION_WORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in ESCALATION_WORDS) + r")\b"
)


def requests_human_handoff(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in HUMAN_HANDOFF_PHRASES)


def has_business_impact(message: str) -> bool:
    lowered = message.lower()
    return (
        any(phrase in lowered for phrase in BUSINESS_IMPACT_PHRASES)
        or _ESCALATION_WORD_PATTERN.search(lowered) is not None
    )


def needs_elevated_access(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in ELEVATED_ACCESS_PHRASES)


def build_ticket(issue_type: str, escalation_needed: bool) -> dict:
    """Ticket fields for a new ticket."""
    mapping = ISSUE_TEAM_MAPPING.get(issue_type, TICKET_DEFAULTS)
    ticket = {
        "priority": mapping["priority"],
        "assigned_team": mapping["assigned_team"],
        "status": STATUS_OPEN,
    }
    if escalation_needed:
        ticket["priority"] = "High"
        ticket["status"] = STATUS_ESCALATION_REQUESTED
    return ticket


def apply_ticket_status(status: str, user_message: str) -> str:
    """Advance the ticket status machine (legacy update_ticket_status).

    Resolution keywords still require explicit confirmation before a
    ticket is resolved. Escalation is decided separately by the service
    using defined criteria, so a failed troubleshooting step alone never
    changes the ticket to an escalation state. Terminal states (Resolved,
    Escalated) cannot regress, and negated phrasing never counts as
    closure.
    """
    if status in TERMINAL_STATUSES:
        return status

    message = user_message.lower()
    negated = any(marker in message for marker in CLOSURE_NEGATIONS)

    if (
        not negated
        and status == STATUS_AWAITING_CONFIRMATION
        and any(keyword in message for keyword in CONFIRMATION_KEYWORDS)
    ):
        return STATUS_RESOLVED

    if not negated and any(keyword in message for keyword in RESOLVED_KEYWORDS):
        return STATUS_AWAITING_CONFIRMATION

    if status == STATUS_OPEN:
        return STATUS_IN_PROGRESS

    return status
