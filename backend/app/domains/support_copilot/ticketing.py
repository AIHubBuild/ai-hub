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

# Escalation phrases (substring match) and single words (word-boundary
# match). Word boundaries prevent false triggers from error codes like
# CRITICAL_PROCESS_DIED (which contains "critical" but is not an
# escalation request).
ESCALATION_PHRASES = [
    "still not working",
    "affecting everyone",
    "cannot work",
    "business impact",
]

ESCALATION_WORDS = ["urgent", "critical", "outage"]

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
STATUS_ESCALATED = "Escalated"

# Terminal states: no keyword may regress a ticket out of them.
TERMINAL_STATUSES = {STATUS_RESOLVED, STATUS_ESCALATED}

_ESCALATION_WORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in ESCALATION_WORDS) + r")\b"
)


def _has_escalation_keywords(message: str) -> bool:
    return (
        any(phrase in message for phrase in ESCALATION_PHRASES)
        or _ESCALATION_WORD_PATTERN.search(message) is not None
    )


def build_ticket(issue_type: str, escalation_needed: bool) -> dict:
    """Ticket fields for a new ticket (legacy generate_ticket logic)."""
    mapping = ISSUE_TEAM_MAPPING.get(issue_type, TICKET_DEFAULTS)
    ticket = {
        "priority": mapping["priority"],
        "assigned_team": mapping["assigned_team"],
        "status": STATUS_OPEN,
    }
    if escalation_needed:
        ticket["priority"] = "High"
    return ticket


def apply_ticket_status(status: str, user_message: str) -> str:
    """Advance the ticket status machine (legacy update_ticket_status).

    Keyword order and semantics are preserved, with three corrections:
    escalation keywords use word boundaries (so error codes like
    CRITICAL_PROCESS_DIED do not trigger escalation); terminal states
    (Resolved, Escalated) cannot regress; and negated phrasing
    ("not fixed", "no thanks, still broken") never counts as closure.
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

    if _has_escalation_keywords(message):
        return STATUS_ESCALATED

    if status == STATUS_OPEN:
        return STATUS_IN_PROGRESS

    return status
