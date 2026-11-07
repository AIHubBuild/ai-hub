"""Authenticated billing routes and the unauthenticated Stripe webhook."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.access import require_verified_email
from app.core.config import Settings, get_app_settings
from app.core.security import AuthUser
from app.db.session import get_db
from app.domains.billing import service
from app.domains.billing.schemas import (
    BillingStatusData,
    BillingStatusResponse,
    CheckoutData,
    CheckoutResponse,
    PortalData,
    PortalResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])


def _error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "message": message},
    )


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> BillingStatusResponse:
    data = service.get_billing_status(session, user, settings)
    return BillingStatusResponse(
        message="Billing status retrieved.",
        data=BillingStatusData(**data),
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> CheckoutResponse:
    try:
        data = service.create_checkout_session(session, user, settings)
    except service.BillingNotConfiguredError as exc:
        raise _error(503, str(exc)) from exc
    except service.AlreadySubscribedError as exc:
        raise _error(409, str(exc)) from exc
    except service.TrialCheckoutPendingError as exc:
        raise _error(409, str(exc)) from exc
    return CheckoutResponse(
        message="Checkout session created.",
        data=CheckoutData(**data),
    )


@router.post("/portal", response_model=PortalResponse)
def create_portal(
    user: AuthUser = Depends(require_verified_email),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> PortalResponse:
    try:
        data = service.create_portal_session(session, user, settings)
    except service.BillingNotConfiguredError as exc:
        raise _error(503, str(exc)) from exc
    except service.NoBillingAccountError as exc:
        raise _error(409, str(exc)) from exc
    return PortalResponse(
        message="Billing portal session created.",
        data=PortalData(**data),
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        processed = service.process_webhook_event(
            session, settings, payload, signature
        )
    except service.BillingNotConfiguredError as exc:
        raise _error(503, str(exc)) from exc
    except service.WebhookSignatureError as exc:
        raise _error(400, str(exc)) from exc
    return {
        "success": True,
        "message": "Webhook received.",
        "data": {"duplicate": not processed},
    }
