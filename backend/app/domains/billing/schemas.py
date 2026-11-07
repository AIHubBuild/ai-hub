"""HTTP schemas for subscription billing."""

from datetime import datetime

from pydantic import BaseModel


class SubscriptionSummary(BaseModel):
    status: str
    price_id: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    cancel_at: datetime | None
    trial_start: datetime | None
    trial_end: datetime | None


class BillingStatusData(BaseModel):
    tier: str
    is_pro: bool
    trial_eligible: bool
    has_billing_account: bool
    price_cents: int
    price_currency: str
    trial_hours: int
    subscription: SubscriptionSummary | None


class BillingStatusResponse(BaseModel):
    success: bool = True
    message: str
    data: BillingStatusData


class CheckoutData(BaseModel):
    url: str
    session_id: str
    trial_applied: bool


class CheckoutResponse(BaseModel):
    success: bool = True
    message: str
    data: CheckoutData


class PortalData(BaseModel):
    url: str


class PortalResponse(BaseModel):
    success: bool = True
    message: str
    data: PortalData
