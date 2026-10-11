"""Tests for the ported ticketing logic (legacy behavior preserved)."""

from app.domains.support_copilot.ticketing import (
    STATUS_AWAITING_CONFIRMATION,
    STATUS_ESCALATED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUS_RESOLVED,
    apply_ticket_status,
    build_ticket,
)


def test_build_ticket_defaults_to_general_it_support():
    ticket = build_ticket("some_unknown_category", escalation_needed=False)

    assert ticket["priority"] == "Medium"
    assert ticket["assigned_team"] == "General IT Support"
    assert ticket["status"] == STATUS_OPEN


def test_build_ticket_security_issue_is_high_priority():
    ticket = build_ticket("security_issue", escalation_needed=False)

    assert ticket["priority"] == "High"
    assert ticket["assigned_team"] == "Security Operations"


def test_build_ticket_password_reset_is_low_priority():
    ticket = build_ticket("password_reset", escalation_needed=False)

    assert ticket["priority"] == "Low"
    assert ticket["assigned_team"] == "Identity Management"


def test_build_ticket_vpn_issue_goes_to_remote_access():
    ticket = build_ticket("vpn_issue", escalation_needed=False)

    assert ticket["priority"] == "Medium"
    assert ticket["assigned_team"] == "Remote Access Team"


def test_build_ticket_escalation_raises_priority():
    ticket = build_ticket("vpn_issue", escalation_needed=True)

    assert ticket["priority"] == "High"


def test_first_follow_up_moves_open_to_in_progress():
    assert (
        apply_ticket_status(STATUS_OPEN, "I tried rebooting") == STATUS_IN_PROGRESS
    )


def test_resolution_keyword_moves_to_awaiting_confirmation():
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "The VPN works now")
        == STATUS_AWAITING_CONFIRMATION
    )


def test_confirmation_after_awaiting_resolves_ticket():
    assert (
        apply_ticket_status(STATUS_AWAITING_CONFIRMATION, "confirmed, fixed")
        == STATUS_RESOLVED
    )


def test_resolved_keyword_does_not_skip_awaiting_confirmation():
    # "working now" alone must not resolve the ticket — legacy two-step.
    assert (
        apply_ticket_status(STATUS_AWAITING_CONFIRMATION, "it is working now")
        == STATUS_AWAITING_CONFIRMATION
    )


def test_escalation_keywords_escalate_ticket():
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "critical outage affecting everyone")
        == STATUS_ESCALATED
    )


def test_error_code_containing_critical_does_not_escalate():
    """CRITICAL_PROCESS_DIED is diagnostic data, not an escalation request."""
    message = (
        "The blue screen shows the error code CRITICAL_PROCESS_DIED "
        "after a Windows update."
    )
    assert apply_ticket_status(STATUS_IN_PROGRESS, message) == STATUS_IN_PROGRESS


def test_standalone_critical_word_does_escalate():
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "this is critical")
        == STATUS_ESCALATED
    )


def test_escalated_ticket_cannot_regress():
    assert (
        apply_ticket_status(STATUS_ESCALATED, "it works now")
        == STATUS_ESCALATED
    )


def test_resolved_ticket_cannot_regress():
    assert (
        apply_ticket_status(STATUS_RESOLVED, "urgent new issue")
        == STATUS_RESOLVED
    )


def test_status_unchanged_without_keywords():
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "hello there")
        == STATUS_IN_PROGRESS
    )
