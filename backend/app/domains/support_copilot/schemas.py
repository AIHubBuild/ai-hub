"""HTTP schemas for the Support Copilot domain.

Requests/responses follow the platform envelope
(`docs/07_API_Design.md` §3.4); message content is bounded to keep
prompts finite and to limit token cost.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 4000

STATUS_ACTIVE = "active"
STATUS_RESOLVED = "resolved"


class SendMessageRequest(BaseModel):
    """Request body for POST /support/sessions/{id}/messages."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank.")
        return stripped


class TicketData(BaseModel):
    ticket_id: str
    priority: str
    assigned_team: str
    status: str


class MessageData(BaseModel):
    role: str
    content: str


class CreateSessionData(BaseModel):
    session_id: str


class CreateSessionResponse(BaseModel):
    success: bool = True
    message: str
    data: CreateSessionData


class SendMessageData(BaseModel):
    session_id: str
    status: str
    issue_type: str | None = None
    ticket: TicketData | None = None
    escalation_needed: bool
    follow_up_question: str | None = None
    response: str


class SendMessageResponse(BaseModel):
    success: bool = True
    message: str
    data: SendMessageData


class SessionDetailData(BaseModel):
    session_id: str
    status: str
    issue_type: str | None = None
    messages: list[MessageData]
    ticket: TicketData | None = None
    created_at: datetime


class SessionDetailResponse(BaseModel):
    success: bool = True
    message: str
    data: SessionDetailData


class TicketListItem(TicketData):
    session_id: str
    issue_type: str | None = None
    created_at: datetime


class TicketListData(BaseModel):
    tickets: list[TicketListItem]


class TicketListResponse(BaseModel):
    success: bool = True
    message: str
    data: TicketListData


class SessionSummary(BaseModel):
    session_id: str
    status: str
    issue_type: str | None = None
    created_at: datetime


class SessionListData(BaseModel):
    sessions: list[SessionSummary]


class SessionListResponse(BaseModel):
    success: bool = True
    message: str
    data: SessionListData
