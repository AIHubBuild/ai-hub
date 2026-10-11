"""Ticket creation and status machine.

Ported from the standalone Copilot's `ticketing.py` (REFACTOR per
`docs/09_Migration_Analysis.md` §3.2): the priority/team mapping and the
keyword-driven status machine are preserved exactly. Ticket IDs are no
longer `random.randint(1000, 9999)` — persistence rows use DB-generated
UUIDs, and the user-facing `INC-` id is derived deterministically from
the UUID (see `service.display_ticket_id`).
"""

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

ESCALATION_KEYWORDS = [
    "still not working",
    "urgent",
    "affecting everyone",
    "critical",
    "outage",
    "cannot work",
    "business impact",
]

# Status values — preserved from the legacy implementation.
STATUS_OPEN = "Open"
STATUS_IN_PROGRESS = "In Progress"
STATUS_AWAITING_CONFIRMATION = "Awaiting Confirmation"
STATUS_RESOLVED = "Resolved"
STATUS_ESCALATED = "Escalated"


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

    Keyword order and semantics are preserved exactly.
    """
    message = user_message.lower()

    if (
        status == STATUS_AWAITING_CONFIRMATION
        and any(keyword in message for keyword in CONFIRMATION_KEYWORDS)
    ):
        return STATUS_RESOLVED

    if any(keyword in message for keyword in RESOLVED_KEYWORDS):
        return STATUS_AWAITING_CONFIRMATION

    if any(keyword in message for keyword in ESCALATION_KEYWORDS):
        return STATUS_ESCALATED

    if status == STATUS_OPEN:
        return STATUS_IN_PROGRESS

    return status
