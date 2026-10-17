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
import re

from sqlalchemy.orm import Session

from app.ai_core import AICore
from app.ai_core.writing_style import normalize_writing
from app.ai_core.providers.openai import ProviderError
from app.ai_core.workflows import WorkflowNotFoundError
from app.domains.support_copilot.knowledge_loader import load_knowledge
from app.domains.support_copilot.state import empty_state
from app.domains.support_copilot.ticketing import (
    CLOSURE_NEGATIONS,
    CONFIRMATION_KEYWORDS,
    GRATITUDE_KEYWORDS,
    RESOLVED_KEYWORDS,
    STATUS_ESCALATED,
    STATUS_ESCALATION_REQUESTED,
    STATUS_RESOLVED,
    apply_ticket_status,
    build_ticket,
    has_business_impact,
    needs_elevated_access,
    requests_human_handoff,
)
from app.domains.support_copilot.workflow import (
    NOT_IT_CLARIFICATION_TEXT,
    ROOT_CAUSE_STEP_ID,
    SUPPORT_WORKFLOW_ID,
    TROUBLESHOOT_STEP_ID,
)
from app.domains.support_copilot.prompts import NOT_AN_IT_ISSUE
from app.models.support import SupportSession, SupportTicket

DOMAIN = "support_copilot"

HISTORY_MESSAGE_LIMIT = 10
MAX_DIAGNOSTIC_ATTEMPTS = 3

ESCALATION_LIMITATION_TEXT = (
    "This workspace does not have a live human handoff integration, so "
    "I cannot confirm that a person has received the ticket. Please "
    "contact your IT service desk directly if you need immediate human "
    "help."
)

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "hiya",
    "howdy",
    "yo",
    "morning",
    "afternoon",
    "evening",
    "greetings",
}

GREETING_PHRASES = (
    "good morning",
    "good afternoon",
    "good evening",
    "hey there",
    "hi there",
    "hello there",
    "what's up",
)

NEW_ISSUE_MARKERS = (
    "new issue",
    "new problem",
    "different issue",
    "different problem",
    "separate issue",
    "another issue",
    "unrelated issue",
    "new question",
)

_VOWELS = set("aeiouyAEIOUY")

GREETING_FIRST_MESSAGE_TEXT = (
    "Hello! I'm the IT Support Copilot. Describe the issue you're "
    "having. For example, a VPN connection problem, a password reset, "
    "or a network issue. I'll open a support ticket and guide you "
    "through troubleshooting."
)

UNCLEAR_MESSAGE_TEXT = (
    "I couldn't quite understand that. Could you rephrase it? For "
    "example: \"I can't connect to the VPN\", \"my laptop keeps "
    "restarting\", or \"I need a password reset\"."
)

AMBIGUOUS_MESSAGE_TEXT = (
    "I can help, but I need a bit more detail. What exactly is "
    "happening? For example: the app or device affected, any error "
    "message, and when it started."
)

# Words that indicate a concrete IT issue. Their presence means a short
# message is specific enough to classify rather than ask for detail.
_ISSUE_HINTS = {
    "access",
    "account",
    "adapter",
    "app",
    "application",
    "backup",
    "blue",
    "browser",
    "computer",
    "connect",
    "connection",
    "crash",
    "dhcp",
    "disk",
    "dns",
    "domain",
    "drive",
    "email",
    "exchange",
    "file",
    "firewall",
    "hardware",
    "hacked",
    "internet",
    "laptop",
    "login",
    "mac",
    "mail",
    "malware",
    "microsoft",
    "monitor",
    "network",
    "onedrive",
    "outlook",
    "password",
    "phishing",
    "printer",
    "reset",
    "router",
    "screen",
    "server",
    "sharepoint",
    "slow",
    "software",
    "teams",
    "update",
    "vpn",
    "wifi",
    "windows",
}

# Single words and short phrases that carry no diagnostic detail.
_VAGUE_WORDS = {
    "broken",
    "bug",
    "error",
    "fault",
    "fix",
    "glitch",
    "help",
    "issue",
    "problem",
    "stuck",
    "weird",
    "wrong",
}

_AMBIGUOUS_PHRASES = {
    "it broke",
    "its broken",
    "it is broken",
    "something broke",
    "something is broken",
    "something is wrong",
    "something wrong",
    "nothing works",
    "not working",
    "it is not working",
    "it isnt working",
    "does not work",
    "doesnt work",
    "please help",
    "i need help",
    "can you help",
    "no idea",
    "not sure",
    "same issue",
    "still broken",
}


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


def _extract_section(content: str, heading: str) -> str:
    """Return the body of a ``### Heading`` section, if present."""
    pattern = re.compile(
        rf"^###\s+{re.escape(heading)}\s*$\n?(.*?)(?=^###\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _count_troubleshooting_attempts(messages: list[dict]) -> int:
    return sum(
        1
        for message in messages
        if message.get("role") == "assistant"
        and _extract_section(message.get("content", ""), "Troubleshooting Response")
    )


def _first_user_message(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _latest_user_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _last_escalation_reason(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        section = _extract_section(message.get("content", ""), "Escalation Status")
        match = re.search(r"Reason:\s*(.+)", section, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _diagnostic_context(messages: list[dict]) -> str:
    """Summarise previous attempts and the user's result for the model.

    The model still receives the bounded conversation history. This
    summary makes it harder to repeat a completed step.
    """
    attempts: list[tuple[str, str]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        step = _extract_section(
            message.get("content", ""), "Troubleshooting Response"
        )
        if not step:
            continue
        result = ""
        for later in messages[index + 1 :]:
            if later.get("role") == "user":
                result = str(later.get("content", "")).strip()
                break
        attempts.append((step, result))

    if not attempts:
        return "No previous troubleshooting attempts."

    lines = ["Previous attempts (do not repeat completed steps):"]
    for number, (step, result) in enumerate(attempts[-4:], start=1):
        lines.append(f"{number}. Copilot: {step[:300]}")
        lines.append(f"   User result: {result or 'not reported yet'}")
    return "\n".join(lines)


def _handoff_status(ticket: SupportTicket | None) -> str:
    if ticket is None:
        return "not_requested"
    if ticket.status == STATUS_ESCALATED:
        return "accepted"
    if ticket.status == STATUS_ESCALATION_REQUESTED:
        return "requested"
    return "not_requested"


def _ticket_details(
    ticket: SupportTicket,
    messages: list[dict],
    *,
    escalation_reason: str = "",
) -> dict:
    """User-facing ticket context derived from the persisted conversation."""
    root_cause = ""
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        section = _extract_section(
            message.get("content", ""), "Root Cause Analysis"
        )
        if section and section.lower() != "pending resolution":
            root_cause = section
            break

    return {
        "ticket_id": display_ticket_id(ticket.id),
        "priority": ticket.priority,
        "assigned_team": ticket.assigned_team,
        "status": ticket.status,
        "reported_issue": _first_user_message(messages),
        "latest_user_update": _latest_user_message(messages),
        "troubleshooting_attempts": _count_troubleshooting_attempts(messages),
        "current_hypothesis": root_cause or "Not confirmed",
        "handoff_status": _handoff_status(ticket),
        "escalation_reason": (
            escalation_reason or _last_escalation_reason(messages) or None
        ),
    }


def ticket_details(
    ticket: SupportTicket, messages: list[dict]
) -> dict:
    """Public accessor for the derived ticket context."""
    return _ticket_details(ticket, messages)


def _escalation_reason(
    *,
    issue_type: str,
    message: str,
    ticket: SupportTicket | None,
    attempts: int,
    previous_reason: str = "",
) -> str:
    """Return a reason when a defined escalation criterion is met."""
    if issue_type == "security_issue":
        return "Security concern reported."
    if requests_human_handoff(message):
        return "Human handoff requested."
    if has_business_impact(message):
        return "Significant business impact reported."
    if needs_elevated_access(message):
        return (
            "The next steps need permissions or expertise outside the "
            "Copilot's access."
        )
    if attempts >= MAX_DIAGNOSTIC_ATTEMPTS:
        return (
            "Repeated troubleshooting steps have not resolved the issue."
        )
    if ticket is not None and ticket.status == STATUS_ESCALATION_REQUESTED:
        return previous_reason or "Escalation already requested."
    return ""


def _request_escalation(ticket: SupportTicket, reason: str) -> None:
    if ticket.status in {STATUS_RESOLVED, STATUS_ESCALATED}:
        return
    ticket.status = STATUS_ESCALATION_REQUESTED
    ticket.priority = "High"


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
    SessionNotFoundError / SessionResolvedError /
    ProviderNotAvailableError / ProviderUnavailableError. On provider
    failure nothing is persisted — the caller may retry the same
    message.

    Conversation policy (deterministic, before any AI call):
    - A resolved session answers gratitude with a polite closure note;
      anything else still asks the user to start a new session.
    - A "fixed" report moves the ticket to Awaiting Confirmation and
      asks for explicit confirmation — without re-running
      troubleshooting.
    - Explicit confirmation resolves the ticket and produces the
      suspected-cause summary.
    - Gratitude elsewhere gets a short acknowledgment.
    """
    session = get_session(db, session_id, user_id)
    ticket = get_ticket_for_session(db, session.id)
    ticket_status = ticket.status if ticket is not None else None
    intent = _detect_intent(message, ticket_status)

    if session.status == "resolved":
        if intent == "gratitude":
            return _append_turn(
                db,
                session,
                ticket,
                message,
                (
                    "You're welcome! Ticket "
                    f"{display_ticket_id(ticket.id)} has been resolved. "
                    "Start a new session if you have another issue."
                ),
            )
        raise SessionResolvedError(session_id)

    if session.issue_type is None:
        if _detect_greeting(message):
            return _append_turn(
                db, session, ticket, message, GREETING_FIRST_MESSAGE_TEXT
            )
        if _is_unclear(message):
            return _append_turn(db, session, ticket, message, UNCLEAR_MESSAGE_TEXT)
        if _is_ambiguous(message):
            return _append_turn(
                db, session, ticket, message, AMBIGUOUS_MESSAGE_TEXT
            )
    else:
        if _detect_greeting(message):
            return _append_turn(
                db,
                session,
                ticket,
                message,
                (
                    f"Hello again! We're still working on your "
                    f"**{session.issue_type}** issue. Give me the latest "
                    "details if it's still happening, or let me know if "
                    "it's resolved so I can close the ticket."
                ),
            )
        if _is_unclear(message):
            return _append_turn(db, session, ticket, message, UNCLEAR_MESSAGE_TEXT)
        if _is_new_issue(message):
            return _orchestrate(
                ai_core, db, session, message, user_id, reclassify=True
            )

    if session.issue_type is not None and intent == "gratitude":
        return _append_turn(
            db,
            session,
            ticket,
            message,
            (
                "You're welcome! Whenever you're ready, let me know if "
                "the issue is resolved so I can close the ticket."
            ),
        )

    if session.issue_type is not None and intent == "fix_report":
        new_status = apply_ticket_status(
            ticket.status if ticket is not None else "Open", message
        )
        if ticket is not None:
            ticket.status = new_status
        return _append_turn(
            db,
            session,
            ticket,
            message,
            (
                "Thanks for the update! The ticket is now marked "
                "**Awaiting Confirmation**. Please confirm: is the issue "
                "fully resolved?"
            ),
        )

    if (
        session.issue_type is not None
        and intent == "confirmation"
        and ticket is not None
    ):
        try:
            return _resolve_turn(ai_core, db, session, ticket, message, user_id)
        except WorkflowNotFoundError as exc:
            raise ProviderNotAvailableError(
                "The AI provider is not configured. Set AI_API_KEY (or DEEPSEEK_API_KEY) "
                "in the environment or .env file to enable support sessions."
            ) from exc
        except ProviderError as exc:
            raise ProviderUnavailableError(
                f"The AI provider failed while running the support session: {exc}"
            ) from exc

    if session.issue_type is not None and ticket is not None:
        existing_messages = list(session.messages or [])
        attempts = _count_troubleshooting_attempts(existing_messages)
        previous_reason = _last_escalation_reason(existing_messages)
        reason = _escalation_reason(
            issue_type=session.issue_type,
            message=message,
            ticket=ticket,
            attempts=attempts,
            previous_reason=previous_reason,
        )
        if reason:
            _request_escalation(ticket, reason)
            response_text = _render_response(
                issue_type=session.issue_type,
                follow_up="",
                resolution="",
                root_cause="",
                escalation_needed=True,
                ticket=ticket,
                first_message=False,
                escalation_reason=reason,
            )
            return _append_turn(
                db,
                session,
                ticket,
                message,
                response_text,
                escalation_reason=reason,
            )

    try:
        return _orchestrate(ai_core, db, session, message, user_id)
    except WorkflowNotFoundError as exc:
        raise ProviderNotAvailableError(
            "The AI provider is not configured. Set AI_API_KEY (or DEEPSEEK_API_KEY) "
            "in the environment or .env file to enable support sessions."
        ) from exc
    except ProviderError as exc:
        raise ProviderUnavailableError(
            f"The AI provider failed while running the support session: {exc}"
        ) from exc


def _detect_greeting(message: str) -> bool:
    """True when the message is a pure greeting rather than a report.

    Messages mixing a greeting with real content ("hi, it's still not
    working") are not greetings: they continue the existing flow.
    """
    lowered = message.lower().strip()
    if lowered in GREETING_PHRASES:
        return True
    words = re.sub(r"[^a-z\s]", " ", lowered).split()
    return bool(words) and all(word in GREETING_WORDS for word in words)


def _is_unclear(message: str) -> bool:
    """True for empty, punctuation-only, or typo-like messages.

    Heuristics: no alphabetic content, fewer than two letters, or a
    string of four or more letters with no vowels (e.g. "hrllj").
    """
    stripped = message.strip()
    if not stripped:
        return True
    if not any(ch.isalpha() for ch in stripped):
        return True
    alpha = re.sub(r"[^a-zA-Z]", "", stripped)
    if len(alpha) < 2:
        return True
    if len(alpha) >= 4 and not _VOWELS.intersection(alpha):
        return True
    if len(alpha) >= 4 and len(set(alpha.lower())) == 1:
        return True
    return False


def _is_ambiguous(message: str) -> bool:
    """True for short messages with no diagnostic detail.

    A first message such as "help" or "something is wrong" cannot be
    classified or troubleshot without guessing, so the Copilot asks for
    specifics instead of calling the provider or opening a ticket.
    Messages containing a concrete issue term ("VPN down", "printer
    offline") are never treated as ambiguous.
    """
    lowered = message.lower().replace("'", "")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    if not lowered:
        return False
    words = lowered.split()
    if set(words) & _ISSUE_HINTS:
        return False
    if lowered in _AMBIGUOUS_PHRASES:
        return True
    return len(words) == 1 and words[0] in _VAGUE_WORDS


def _is_new_issue(message: str) -> bool:
    """True when the user explicitly signals a new, separate issue."""
    lowered = message.lower()
    return any(marker in lowered for marker in NEW_ISSUE_MARKERS)


def _detect_intent(message: str, ticket_status: str | None) -> str:
    """Classify the user's conversational intent.

    Returns one of: "confirmation", "fix_report", "gratitude",
    "troubleshooting". Negated phrasing ("not fixed", "no thanks, still
    broken") never counts as closure.
    """
    lowered = message.lower()
    if any(marker in lowered for marker in CLOSURE_NEGATIONS):
        return "troubleshooting"

    if (
        ticket_status == "Awaiting Confirmation"
        and any(keyword in lowered for keyword in CONFIRMATION_KEYWORDS)
    ):
        return "confirmation"

    if any(keyword in lowered for keyword in RESOLVED_KEYWORDS):
        return "fix_report"

    if any(keyword in lowered for keyword in GRATITUDE_KEYWORDS):
        return "gratitude"

    return "troubleshooting"


def _append_turn(
    db: Session,
    session: SupportSession,
    ticket: SupportTicket | None,
    message: str,
    response_text: str,
    *,
    escalation_reason: str = "",
) -> dict:
    """Persist a user/assistant turn without calling the AI provider."""
    response_text = normalize_writing(response_text)
    messages = list(session.messages or [])
    messages.append({"role": "user", "content": message})
    messages.append({"role": "assistant", "content": response_text})
    session.messages = messages
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    if ticket is not None:
        db.refresh(ticket)
    return _payload(
        session,
        ticket,
        response_text,
        False,
        escalation_reason=escalation_reason,
    )


def _resolve_turn(
    ai_core: AICore,
    db: Session,
    session: SupportSession,
    ticket: SupportTicket,
    message: str,
    user_id: str,
) -> dict:
    """Resolve the ticket: suspected-cause summary + confirmation note."""
    messages = list(session.messages or [])
    history = _conversation_history(messages)
    state = empty_state()
    state["issue_type"] = session.issue_type or ""
    state["conversation_history"] = _conversation_history(
        messages, [{"role": "user", "content": message}]
    )
    root_cause_run = ai_core.workflows.run(
        ROOT_CAUSE_STEP_ID,
        dict(state),
        user_id=user_id,
        domain=DOMAIN,
    )
    root_cause = root_cause_run.output_state.get("root_cause_summary") or ""

    ticket.status = "Resolved"
    session.status = "resolved"

    response_text = _render_response(
        issue_type=session.issue_type or "",
        follow_up="",
        resolution=(
            f"Thank you for confirming. Ticket "
            f"{display_ticket_id(ticket.id)} has been marked as Resolved."
        ),
        root_cause=root_cause,
        escalation_needed=False,
        ticket=ticket,
        first_message=False,
    )
    return _append_turn(db, session, ticket, message, response_text)


def _payload(
    session: SupportSession,
    ticket: SupportTicket | None,
    response_text: str,
    escalation_needed: bool,
    *,
    escalation_reason: str = "",
) -> dict:
    messages = list(session.messages or [])
    return {
        "session_id": session.id,
        "status": session.status,
        "issue_type": session.issue_type,
        "ticket": (
            _ticket_details(
                ticket,
                messages,
                escalation_reason=escalation_reason,
            )
            if ticket is not None
            else None
        ),
        "escalation_needed": escalation_needed
        or (ticket is not None and ticket.status == STATUS_ESCALATION_REQUESTED),
        "follow_up_question": None,
        "response": response_text,
    }


def _orchestrate(
    ai_core: AICore,
    db: Session,
    session: SupportSession,
    message: str,
    user_id: str,
    *,
    reclassify: bool = False,
) -> dict:
    messages = list(session.messages or [])
    history = _conversation_history(messages)
    attempts = _count_troubleshooting_attempts(messages)
    previous_reason = _last_escalation_reason(messages)

    state = empty_state()
    state["user_issue"] = message
    state["conversation_history"] = history
    state["diagnostic_context"] = _diagnostic_context(messages)

    if session.issue_type is None or reclassify:
        first_message = True
        run = ai_core.workflows.run(
            SUPPORT_WORKFLOW_ID,
            dict(state),
            user_id=user_id,
            domain=DOMAIN,
        )
        out = run.output_state
        issue_type = out.get("issue_type") or "general"
        if issue_type == NOT_AN_IT_ISSUE:
            # Not an IT problem: clarify without creating a ticket or
            # an incident classification. The session stays unclassified
            # so the next message is classified afresh.
            return _append_turn(
                db,
                session,
                None,
                message,
                out.get("resolution") or NOT_IT_CLARIFICATION_TEXT,
            )
        session.issue_type = issue_type
        follow_up = out.get("follow_up_question") or ""
        # The first turn diagnoses and asks a focused question. It does
        # not prescribe a fix before the user answers.
        resolution = ""
        escalation_needed = bool(out.get("escalation_needed"))
        escalation_reason = _escalation_reason(
            issue_type=issue_type,
            message=message,
            ticket=None,
            attempts=0,
        )
        if escalation_reason:
            escalation_needed = True
    else:
        first_message = False
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
        escalation_reason = ""

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
        if escalation_reason:
            _request_escalation(ticket, escalation_reason)
    else:
        if reclassify:
            fields = build_ticket(issue_type, escalation_needed)
            ticket.issue_type = issue_type
            ticket.priority = fields["priority"]
            ticket.assigned_team = fields["assigned_team"]
            ticket.status = fields["status"]
        if escalation_reason:
            _request_escalation(ticket, escalation_reason)
        elif ticket.status != STATUS_ESCALATION_REQUESTED:
            ticket.status = apply_ticket_status(ticket.status, message)

    root_cause = ""
    if ticket.status == STATUS_RESOLVED:
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
    elif ticket.status == STATUS_ESCALATED:
        escalation_reason = (
            escalation_reason or previous_reason or "Human handoff accepted."
        )
        resolution = ""

    response_text = _render_response(
        issue_type=issue_type,
        follow_up=follow_up,
        resolution=resolution,
        root_cause=root_cause,
        escalation_needed=escalation_needed,
        ticket=ticket,
        first_message=first_message,
        escalation_reason=escalation_reason,
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
        "ticket": _ticket_details(
            ticket,
            messages,
            escalation_reason=escalation_reason,
        ),
        "escalation_needed": escalation_needed
        or ticket.status == STATUS_ESCALATION_REQUESTED,
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
    first_message: bool,
    escalation_reason: str = "",
) -> str:
    """Assistant message block.

    The ticket row is the single authoritative source for status and
    escalation. "Escalation Requested" never means a human accepted the
    ticket. The classification section appears only on the first message.
    """
    sections: list[str] = []
    if first_message:
        sections.append(f"### Issue Classification\n{issue_type}")
        sections.append(
            f"### Follow-Up Question\n"
            f"{follow_up if follow_up else 'No follow-up question'}"
        )
    if resolution:
        sections.append(f"### Troubleshooting Response\n{resolution}")
    if root_cause:
        sections.append(f"### Root Cause Analysis\n{root_cause}")

    if ticket.status == STATUS_ESCALATION_REQUESTED:
        reason = f"\nReason: {escalation_reason}" if escalation_reason else ""
        sections.append(
            "### Escalation Status\n"
            f"Escalation requested for {ticket.assigned_team}. "
            "No human engineer has accepted the ticket yet."
            f"{reason}\n"
            f"{ESCALATION_LIMITATION_TEXT}"
        )
    elif ticket.status == STATUS_ESCALATED:
        sections.append(
            "### Escalation Status\n"
            f"A human handoff has been accepted by {ticket.assigned_team}."
        )
    elif escalation_needed:
        sections.append(
            "### Escalation Status\n"
            "This issue meets the escalation criteria. No human handoff "
            "has been accepted yet."
        )
    else:
        sections.append("### Escalation Status\nNo escalation requested.")

    sections.append(
        f"### Support Ticket\n"
        f"- Ticket ID: {display_ticket_id(ticket.id)}\n"
        f"- Priority: {ticket.priority}\n"
        f"- Assigned Team: {ticket.assigned_team}\n"
        f"- Status: {ticket.status}\n"
        f"- Handoff: {_handoff_status(ticket).replace('_', ' ')}"
    )
    return "\n\n".join(sections)
