"""Administrative mutation schemas."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

IncidentPriority = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal[
    "open", "investigating", "waiting_for_information", "resolved", "closed"
]
EntitlementTier = Literal["free", "pro"]


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    category: str = Field(min_length=1, max_length=64)
    priority: IncidentPriority = "medium"
    status: Literal["open", "investigating", "waiting_for_information"] = "open"
    linked_run_id: UUID | None = None
    linked_user_id: UUID | None = None
    assigned_admin_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("title must be at least 3 non-whitespace characters.")
        return stripped

    @field_validator("description", "category")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class IncidentUpdate(BaseModel):
    status: IncidentStatus | None = None
    priority: IncidentPriority | None = None
    assigned_admin_id: UUID | None = None
    resolution_summary: str | None = Field(None, max_length=10000)

    @model_validator(mode="after")
    def status_and_priority_must_not_be_null(self) -> "IncidentUpdate":
        for field_name in ("status", "priority"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null.")
        return self


class EntitlementUpdate(BaseModel):
    tier: EntitlementTier
    limits: dict[str, Any] | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("reason must be at least 3 non-whitespace characters.")
        return stripped
