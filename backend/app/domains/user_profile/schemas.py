"""HTTP schemas for the authenticated user's profile."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PHONE_CHARS = re.compile(r"^[+0-9()\s-]+$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


class ProfileUpsert(BaseModel):
    """Create or replace the current user's profile.

    ``user_id`` is deliberately not accepted. The authenticated JWT subject
    is the only source of profile ownership.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=100)
    career_goal: str | None = Field(default=None, max_length=200)
    marketing_consent: bool = False
    terms_accepted: bool = False
    privacy_accepted: bool = False

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("full_name must be at least 2 characters.")
        return stripped

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        stripped = value.strip()
        digits = re.sub(r"\D", "", stripped)
        if not _PHONE_CHARS.fullmatch(stripped) or not 7 <= len(digits) <= 15:
            raise ValueError("phone must contain 7 to 15 digits.")
        return stripped

    @field_validator("country_code")
    @classmethod
    def country_code_must_be_iso_alpha_2(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        stripped = value.strip().upper()
        if not _COUNTRY_CODE.fullmatch(stripped):
            raise ValueError("country_code must be a two-letter country code.")
        return stripped

    @field_validator("city")
    @classmethod
    def city_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()

    @field_validator("career_goal")
    @classmethod
    def career_goal_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class ProfileData(BaseModel):
    user_id: str
    full_name: str
    phone: str | None
    country_code: str | None
    city: str | None
    career_goal: str | None
    marketing_consent: bool
    terms_accepted_at: datetime
    terms_version: str
    privacy_accepted_at: datetime
    privacy_version: str
    created_at: datetime
    updated_at: datetime
    email: str | None
    email_verified: bool


class ProfileResponse(BaseModel):
    success: bool = True
    message: str
    data: ProfileData
