"""Tests for the ported ticketing logic (legacy behavior preserved)."""

from app.domains.support_copilot.ticketing import (
    STATUS_AWAITING_CONFIRMATION,
    STATUS_ESCALATED,
    STATUS_ESCALATION_REQUESTED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUS_RESOLVED,
    apply_ticket_status,
    build_ticket,
    has_business_impact,
    needs_elevated_access,
    requests_human_handoff,
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


def test_build_ticket_escalation_raises_priority_and_marks_requested():
    ticket = build_ticket("vpn_issue", escalation_needed=True)

    assert ticket["priority"] == "High"
    assert ticket["status"] == STATUS_ESCALATION_REQUESTED


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


def test_status_machine_does_not_escalate_on_failure_keywords_alone():
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "I restarted it but it is still not working")
        == STATUS_IN_PROGRESS
    )
    assert (
        apply_ticket_status(STATUS_IN_PROGRESS, "critical outage affecting everyone")
        == STATUS_IN_PROGRESS
    )


def test_business_impact_and_handoff_criteria_are_detected():
    assert has_business_impact("This is a critical outage affecting everyone.")
    assert not has_business_impact(
        "The blue screen shows CRITICAL_PROCESS_DIED after an update."
    )
    assert requests_human_handoff("I need to speak to a human")
    assert needs_elevated_access("I do not have admin rights on this laptop")


def test_escalation_requested_is_not_accepted_escalation():
    assert STATUS_ESCALATION_REQUESTED != STATUS_ESCALATED
    assert (
        apply_ticket_status(STATUS_ESCALATION_REQUESTED, "still not working")
        == STATUS_ESCALATION_REQUESTED
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
