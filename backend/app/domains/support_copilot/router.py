"""Support Copilot API routes.

Endpoints per `docs/09_Migration_Analysis.md` §4, mounted under
`/api/v1/support`: session create, message send, session detail, and
ticket listing. All endpoints are protected: they require a valid
Supabase JWT and are scoped to the authenticated user — cross-user
access yields 404, identical to a missing resource.

Errors map to:
- 401 missing/invalid/expired token
- 404 unknown session (including other users' sessions)
- 409 message sent to a resolved session
- 422 invalid or oversized message
- 502 AI provider failure during a run
- 503 AI provider not configured (no AI_API_KEY / DEEPSEEK_API_KEY)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_core import AICore, get_ai_core
from app.core.access import require_complete_profile
from app.core.security import AuthUser
from app.db.session import get_db
from app.domains.support_copilot import service
from app.domains.support_copilot.schemas import (
    CreateSessionData,
    CreateSessionResponse,
    MessageData,
    SendMessageRequest,
    SendMessageResponse,
    SessionDetailData,
    SessionDetailResponse,
    SessionListData,
    SessionListResponse,
    SessionSummary,
    TicketData,
    TicketListItem,
    TicketListResponse,
)
from app.domains.support_copilot.service import (
    ProviderNotAvailableError,
    ProviderUnavailableError,
    SessionNotFoundError,
    SessionResolvedError,
)

router = APIRouter(prefix="/support", tags=["support"])


def _error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "message": message},
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


@router.post("/sessions", status_code=201, response_model=CreateSessionResponse)
def create_support_session(
    session: Session = Depends(get_db),
    user: AuthUser = Depends(require_complete_profile),
) -> CreateSessionResponse:
    created = service.create_session(session, user.id)
    return CreateSessionResponse(
        message="Support session created.",
        data=CreateSessionData(session_id=created.id),
    )


@router.post(
    "/sessions/{session_id}/messages",
    status_code=201,
    response_model=SendMessageResponse,
)
def send_support_message(
    session_id: str,
    body: SendMessageRequest,
    session: Session = Depends(get_db),
    ai_core: AICore = Depends(get_ai_core),
    user: AuthUser = Depends(require_complete_profile),
) -> SendMessageResponse:
    if not _is_uuid(session_id):
        raise _error(404, "Support session not found.")

    try:
        payload = service.send_message(
            ai_core,
            session,
            session_id=session_id,
            message=body.message,
            user_id=user.id,
        )
    except SessionNotFoundError as exc:
        raise _error(404, "Support session not found.") from exc
    except SessionResolvedError as exc:
        raise _error(409, "This support session is resolved. Start a new session.") from exc
    except ProviderNotAvailableError as exc:
        raise _error(503, str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise _error(502, str(exc)) from exc

    return SendMessageResponse(
        message="Message processed.",
        data=payload,
    )


@router.get("/sessions", response_model=SessionListResponse)
def list_support_sessions(
    session: Session = Depends(get_db),
    user: AuthUser = Depends(require_complete_profile),
) -> SessionListResponse:
    sessions = service.list_sessions(session, user.id)
    return SessionListResponse(
        message="Support sessions retrieved.",
        data=SessionListData(
            sessions=[
                SessionSummary(
                    session_id=item.id,
                    status=item.status,
                    issue_type=item.issue_type,
                    created_at=item.created_at,
                )
                for item in sessions
            ]
        ),
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_support_session(
    session_id: str,
    session: Session = Depends(get_db),
    user: AuthUser = Depends(require_complete_profile),
) -> SessionDetailResponse:
    if not _is_uuid(session_id):
        raise _error(404, "Support session not found.")

    try:
        support_session = service.get_session(session, session_id, user.id)
    except SessionNotFoundError as exc:
        raise _error(404, "Support session not found.") from exc

    ticket = service.get_ticket_for_session(session, support_session.id)
    return SessionDetailResponse(
        message="Support session retrieved.",
        data=SessionDetailData(
            session_id=support_session.id,
            status=support_session.status,
            issue_type=support_session.issue_type,
            messages=[
                MessageData(role=m["role"], content=m["content"])
                for m in (support_session.messages or [])
            ],
            ticket=(
                TicketData(
                    **service.ticket_details(
                        ticket, support_session.messages or []
                    )
                )
                if ticket is not None
                else None
            ),
            created_at=support_session.created_at,
        ),
    )


@router.get("/tickets", response_model=TicketListResponse)
def list_support_tickets(
    session: Session = Depends(get_db),
    user: AuthUser = Depends(require_complete_profile),
) -> TicketListResponse:
    tickets = service.list_tickets(session, user.id)
    return TicketListResponse(
        message="Tickets retrieved.",
        data={
            "tickets": [
                TicketListItem(
                    ticket_id=service.display_ticket_id(ticket.id),
                    session_id=ticket.session_id,
                    issue_type=ticket.issue_type,
                    priority=ticket.priority,
                    assigned_team=ticket.assigned_team,
                    status=ticket.status,
                    created_at=ticket.created_at,
                )
                for ticket in tickets
            ]
        },
    )
