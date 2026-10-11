"""Support Copilot session service.

Moves the legacy Streamlit orchestration into a user-scoped service:
- First message: run the full ported graph (classify → route → KB →
  follow-up → troubleshoot / escalate) and generate the ticket.
- Follow-up messages: reuse the stored issue type, run the standalone
  troubleshoot step, advance the ticket status machine, and generate the
  root-cause summary when the ticket resolves.

Every AI invocation goes through ai_core's workflow runner (run records
persisted per user); every read is filtered by the authenticated user id
so cross-user access yields the same not-found error as missing records.
Conversation history passed to prompts is bounded to the most recent
messages.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai_core import AICore
from app.ai_core.providers.openai import ProviderError
from app.ai_core.workflows import WorkflowNotFoundError
from app.domains.support_copilot.knowledge_loader import load_knowledge
from app.domains.support_copilot.state import empty_state
from app.domains.support_copilot.ticketing import (
    apply_ticket_status,
    build_ticket,
)
from app.domains.support_copilot.workflow import (
    ROOT_CAUSE_STEP_ID,
    SUPPORT_WORKFLOW_ID,
    TROUBLESHOOT_STEP_ID,
)
from app.models.support import SupportSession, SupportTicket

DOMAIN = "support_copilot"

HISTORY_MESSAGE_LIMIT = 10


class SessionNotFoundError(KeyError):
    """No session exists under the requested id for the requesting user."""


class SessionResolvedError(RuntimeError):
    """The session is resolved and no longer accepts messages."""


class ProviderNotAvailableError(RuntimeError):
    """The AI provider (or the workflow) is not configured."""


class ProviderUnavailableError(RuntimeError):
    """The AI provider failed during a run."""


def display_ticket_id(ticket_id: str) -> str:
    """User-facing ticket reference derived from the DB UUID."""
    return f"INC-{ticket_id[:8].upper()}"


def create_session(db: Session, user_id: str) -> SupportSession:
    session = SupportSession(user_id=user_id, messages=[])
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str, user_id: str) -> SupportSession:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.id == session_id, SupportSession.user_id == user_id)
        .first()
    )
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def get_ticket_for_session(
    db: Session, session_id: str
) -> SupportTicket | None:
    return (
        db.query(SupportTicket)
        .filter(SupportTicket.session_id == session_id)
        .first()
    )


def _conversation_history(messages: list[dict], extra: list[dict] | None = None) -> str:
    window = list(messages[-HISTORY_MESSAGE_LIMIT:])
    if extra:
        window = window + list(extra)
    return "\n".join(f"{m['role']}: {m['content']}" for m in window)


def send_message(
    ai_core: AICore,
    db: Session,
    *,
    session_id: str,
    message: str,
    user_id: str,
) -> dict:
    """Append a user message and produce the assistant response.

    Returns the response payload consumed by the API layer. Raises
    SessionNotFoundError / ProviderNotAvailableError /
    ProviderUnavailableError. On provider failure nothing is persisted —
    the caller may retry the same message.
    """
    session = get_session(db, session_id, user_id)
    if session.status == "resolved":
        raise SessionResolvedError(session_id)

    try:
        return _orchestrate(ai_core, db, session, message, user_id)
    except WorkflowNotFoundError as exc:
        raise ProviderNotAvailableError(
            "The AI provider is not configured. Set OPENAI_API_KEY "
            "in the environment or .env file to enable support sessions."
        ) from exc
    except ProviderError as exc:
        raise ProviderUnavailableError(
            f"The AI provider failed while running the support session: {exc}"
        ) from exc


def _orchestrate(
    ai_core: AICore,
    db: Session,
    session: SupportSession,
    message: str,
    user_id: str,
) -> dict:
    messages = list(session.messages or [])
    history = _conversation_history(messages)

    state = empty_state()
    state["user_issue"] = message
    state["conversation_history"] = history

    if session.issue_type is None:
        run = ai_core.workflows.run(
            SUPPORT_WORKFLOW_ID,
            dict(state),
            user_id=user_id,
            domain=DOMAIN,
        )
        out = run.output_state
        issue_type = out.get("issue_type") or "general"
        session.issue_type = issue_type
        follow_up = out.get("follow_up_question") or ""
        resolution = out.get("resolution") or ""
        escalation_needed = bool(out.get("escalation_needed"))
    else:
        issue_type = session.issue_type
        state["issue_type"] = issue_type
        state["knowledge_base"] = load_knowledge(issue_type)
        run = ai_core.workflows.run(
            TROUBLESHOOT_STEP_ID,
            dict(state),
            user_id=user_id,
            domain=DOMAIN,
        )
        out = run.output_state
        resolution = out.get("resolution") or ""
        follow_up = ""
        escalation_needed = False

    ticket = get_ticket_for_session(db, session.id)
    if ticket is None:
        fields = build_ticket(issue_type, escalation_needed)
        ticket = SupportTicket(
            session_id=session.id,
            user_id=user_id,
            issue_type=issue_type,
            **fields,
        )
        db.add(ticket)
        db.flush()
    else:
        ticket.status = apply_ticket_status(ticket.status, message)

    root_cause = ""
    if ticket.status == "Resolved":
        root_cause_state = dict(state)
        root_cause_state["issue_type"] = issue_type
        root_cause_state["conversation_history"] = _conversation_history(
            messages, [{"role": "user", "content": message}]
        )
        root_cause_run = ai_core.workflows.run(
            ROOT_CAUSE_STEP_ID,
            root_cause_state,
            user_id=user_id,
            domain=DOMAIN,
        )
        root_cause = root_cause_run.output_state.get("root_cause_summary") or ""
        resolution = (
            f"Thank you for confirming. Ticket "
            f"{display_ticket_id(ticket.id)} has been marked as Resolved."
        )
        session.status = "resolved"
    elif ticket.status == "Escalated":
        resolution = (
            f"Ticket {display_ticket_id(ticket.id)} has been escalated to "
            f"{ticket.assigned_team}."
        )

    response_text = _render_response(
        issue_type=issue_type,
        follow_up=follow_up,
        resolution=resolution,
        root_cause=root_cause,
        escalation_needed=escalation_needed,
        ticket=ticket,
    )

    messages.append({"role": "user", "content": message})
    messages.append({"role": "assistant", "content": response_text})
    session.messages = messages
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)

    return {
        "session_id": session.id,
        "status": session.status,
        "issue_type": session.issue_type,
        "ticket": {
            "ticket_id": display_ticket_id(ticket.id),
            "priority": ticket.priority,
            "assigned_team": ticket.assigned_team,
            "status": ticket.status,
        },
        "escalation_needed": escalation_needed,
        "follow_up_question": follow_up,
        "response": response_text,
    }


def list_sessions(db: Session, user_id: str) -> list[SupportSession]:
    return (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id)
        .order_by(SupportSession.created_at.desc())
        .all()
    )


def list_tickets(db: Session, user_id: str) -> list[SupportTicket]:
    return (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )


def _render_response(
    *,
    issue_type: str,
    follow_up: str,
    resolution: str,
    root_cause: str,
    escalation_needed: bool,
    ticket: SupportTicket,
) -> str:
    """Legacy Streamlit markdown response block, preserved verbatim."""
    return f"""
### Issue Classification
{issue_type}

### Follow-Up Question
{follow_up if follow_up else 'No follow-up question'}

### Troubleshooting Response
{resolution}

### Root Cause Analysis
{root_cause if root_cause else 'Pending resolution'}

### Escalation Status
{"Escalated to IT Support Team" if escalation_needed else "No escalation required"}

### Support Ticket
- Ticket ID: {display_ticket_id(ticket.id)}
- Priority: {ticket.priority}
- Assigned Team: {ticket.assigned_team}
- Status: {ticket.status}
""".strip()
