"""Stripe Checkout, Customer Portal, webhooks, and entitlement sync.

Security rules:
- The Stripe secret key and webhook secret are server-side only.
- Checkout and portal sessions are created only for the authenticated user.
- Pro access is derived from backend-verified subscription state, never
  from a request body or frontend flag.
- Webhook signatures are verified before any state is written.
- Webhook events are idempotent by Stripe event id.
"""

import math
import time
from datetime import datetime, timezone
from typing import Any

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import AuthUser
from app.models.admin import UserEntitlement
from app.models.billing import (
    StripeCustomer,
    StripeSubscription,
    StripeWebhookEvent,
)

# Both an active paid subscription and an active 24-hour trial grant Pro
# access. Expired trials and non-paying states downgrade to Free when Stripe
# reports a status outside this set.
PRO_STATUSES = frozenset({"active", "trialing"})
BLOCKING_STATUSES = frozenset({"active", "trialing", "past_due", "unpaid"})

DEFAULT_SUCCESS_PATH = "/billing?checkout=success"
DEFAULT_CANCEL_PATH = "/billing?checkout=cancelled"
DEFAULT_PORTAL_RETURN_PATH = "/billing?portal=return"


class BillingNotConfiguredError(RuntimeError):
    """Stripe billing is not configured for this environment."""


class AlreadySubscribedError(RuntimeError):
    """The user already has a subscription that blocks a new checkout."""


class NoBillingAccountError(RuntimeError):
    """The user has no Stripe customer yet."""


class WebhookSignatureError(RuntimeError):
    """The Stripe webhook signature or payload was invalid."""


class PriceVerificationError(RuntimeError):
    """The configured Stripe Price does not match the Pro plan settings."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _configure_secret(settings: Settings) -> None:
    if not settings.stripe_secret_key:
        raise BillingNotConfiguredError(
            "Stripe billing is not configured."
        )
    stripe.api_key = settings.stripe_secret_key


def _configure_checkout(settings: Settings) -> None:
    _configure_secret(settings)
    if not settings.stripe_price_id:
        raise BillingNotConfiguredError(
            "Stripe billing is not configured."
        )


def validate_price_object(price: Any, settings: Settings) -> dict[str, Any]:
    """Validate a Stripe Price object against the configured Pro plan.

    This is a pure check used by the verification script and tests. The
    actual charge always comes from Stripe's Price, never from this app.
    """
    price_id = price.get("id")
    if not price_id:
        raise PriceVerificationError("Stripe Price is missing an id.")
    if price_id != settings.stripe_price_id:
        raise PriceVerificationError(
            "Stripe Price id does not match STRIPE_PRICE_ID."
        )
    if price.get("active") is False:
        raise PriceVerificationError("Stripe Price is inactive.")
    if price.get("type") != "recurring":
        raise PriceVerificationError("Stripe Price must be recurring.")
    recurring = price.get("recurring") or {}
    if recurring.get("interval") != "month":
        raise PriceVerificationError(
            "Stripe Price interval must be monthly."
        )
    if int(recurring.get("interval_count") or 1) != 1:
        raise PriceVerificationError(
            "Stripe Price interval count must be 1."
        )
    unit_amount = price.get("unit_amount")
    if unit_amount is None or int(unit_amount) != int(
        settings.stripe_pro_price_cents
    ):
        raise PriceVerificationError(
            "Stripe Price amount does not match STRIPE_PRO_PRICE_CENTS."
        )
    currency = (price.get("currency") or "").lower()
    if currency != settings.stripe_pro_price_currency.lower():
        raise PriceVerificationError(
            "Stripe Price currency does not match "
            "STRIPE_PRO_PRICE_CURRENCY."
        )
    return {
        "id": price_id,
        "unit_amount": int(unit_amount),
        "currency": currency,
        "interval": recurring.get("interval"),
        "interval_count": int(recurring.get("interval_count") or 1),
        "active": bool(price.get("active", True)),
    }


def fetch_and_validate_price(settings: Settings) -> dict[str, Any]:
    """Retrieve the configured Price from Stripe and validate it."""
    _configure_secret(settings)
    if not settings.stripe_price_id:
        raise BillingNotConfiguredError(
            "Stripe billing is not configured."
        )
    price = stripe.Price.retrieve(settings.stripe_price_id)
    return validate_price_object(price, settings)


def _frontend_url(settings: Settings, path: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}{path}"


def _first_item(subscription: Any) -> Any:
    items = subscription.get("items") or {}
    data = items.get("data") or []
    return data[0] if data else {}


def _price_id(subscription: Any) -> str | None:
    price = _first_item(subscription).get("price") or {}
    value = price.get("id")
    return value if isinstance(value, str) else None


def _period_value(subscription: Any, field: str) -> Any:
    if subscription.get(field) is not None:
        return subscription.get(field)
    return _first_item(subscription).get(field)


def get_or_create_customer(
    session: Session, user: AuthUser, settings: Settings
) -> StripeCustomer:
    """Return the user's Stripe customer, creating it once if needed."""
    customer = session.get(StripeCustomer, user.id)
    if customer is not None:
        return customer

    _configure_secret(settings)
    kwargs: dict[str, Any] = {"metadata": {"user_id": user.id}}
    if user.email:
        kwargs["email"] = user.email
    created = stripe.Customer.create(**kwargs)
    customer = StripeCustomer(
        user_id=user.id,
        stripe_customer_id=created["id"],
        email=user.email,
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def _blocking_subscription(
    session: Session, user_id: str
) -> StripeSubscription | None:
    return (
        session.query(StripeSubscription)
        .filter(
            StripeSubscription.user_id == user_id,
            StripeSubscription.status.in_(BLOCKING_STATUSES),
        )
        .order_by(StripeSubscription.updated_at.desc())
        .first()
    )


def trial_eligible(
    session: Session, user: AuthUser, customer: StripeCustomer | None
) -> bool:
    """A single 24-hour trial per verified user, never on an active plan."""
    if not user.email_verified:
        return False
    if customer is not None and customer.trial_used_at is not None:
        return False
    if (
        session.query(StripeSubscription)
        .filter(
            StripeSubscription.user_id == user.id,
            StripeSubscription.trial_start.isnot(None),
        )
        .first()
        is not None
    ):
        return False
    return _blocking_subscription(session, user.id) is None


def _trial_days(settings: Settings) -> int:
    # Stripe trials are expressed in whole days. 24 hours == 1 day.
    return max(1, math.ceil(settings.stripe_trial_hours / 24))


def create_checkout_session(
    session: Session, user: AuthUser, settings: Settings
) -> dict[str, Any]:
    _configure_checkout(settings)
    try:
        fetch_and_validate_price(settings)
    except PriceVerificationError as exc:
        raise BillingNotConfiguredError(
            "Stripe price configuration is invalid."
        ) from exc
    if _blocking_subscription(session, user.id) is not None:
        raise AlreadySubscribedError(
            "An active subscription already exists for this account."
        )

    customer = get_or_create_customer(session, user, settings)
    eligible = trial_eligible(session, user, customer)

    subscription_data: dict[str, Any] = {
        "metadata": {"user_id": user.id},
    }
    if eligible:
        subscription_data["trial_period_days"] = _trial_days(settings)

    checkout = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer.stripe_customer_id,
        client_reference_id=user.id,
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=_frontend_url(settings, DEFAULT_SUCCESS_PATH),
        cancel_url=_frontend_url(settings, DEFAULT_CANCEL_PATH),
        subscription_data=subscription_data,
    )

    if eligible:
        customer.trial_used_at = _utcnow()
        session.commit()

    return {
        "url": checkout["url"],
        "session_id": checkout["id"],
        "trial_applied": eligible,
    }


def create_portal_session(
    session: Session, user: AuthUser, settings: Settings
) -> dict[str, str]:
    _configure_secret(settings)
    customer = session.get(StripeCustomer, user.id)
    if customer is None:
        raise NoBillingAccountError(
            "No billing account exists for this user yet."
        )
    portal = stripe.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=_frontend_url(settings, DEFAULT_PORTAL_RETURN_PATH),
    )
    return {"url": portal["url"]}


def _subscription_summary(
    subscription: StripeSubscription | None,
) -> dict[str, Any] | None:
    if subscription is None:
        return None
    return {
        "status": subscription.status,
        "price_id": subscription.price_id,
        "current_period_end": subscription.current_period_end,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "cancel_at": subscription.cancel_at,
        "trial_start": subscription.trial_start,
        "trial_end": subscription.trial_end,
    }


def get_billing_status(
    session: Session, user: AuthUser, settings: Settings
) -> dict[str, Any]:
    entitlement = session.get(UserEntitlement, user.id)
    tier = entitlement.tier if entitlement is not None else "free"
    customer = session.get(StripeCustomer, user.id)
    subscription = (
        session.query(StripeSubscription)
        .filter(StripeSubscription.user_id == user.id)
        .order_by(StripeSubscription.updated_at.desc())
        .first()
    )
    return {
        "tier": tier,
        "is_pro": tier == "pro",
        "trial_eligible": trial_eligible(session, user, customer),
        "has_billing_account": customer is not None,
        "price_cents": settings.stripe_pro_price_cents,
        "price_currency": settings.stripe_pro_price_currency,
        "trial_hours": settings.stripe_trial_hours,
        "subscription": _subscription_summary(subscription),
    }


def _resolve_customer_and_user(
    session: Session, subscription: Any
) -> tuple[str | None, StripeCustomer | None]:
    customer_id = subscription.get("customer")
    metadata = subscription.get("metadata") or {}
    user_id = metadata.get("user_id")
    customer = None
    if isinstance(customer_id, str):
        customer = (
            session.query(StripeCustomer)
            .filter(StripeCustomer.stripe_customer_id == customer_id)
            .one_or_none()
        )
    if not user_id and customer is not None:
        user_id = customer.user_id
    if not isinstance(user_id, str) or not user_id:
        return None, customer
    if customer is None and isinstance(customer_id, str):
        customer = StripeCustomer(
            user_id=user_id,
            stripe_customer_id=customer_id,
            email=None,
        )
        session.add(customer)
        session.flush()
    return user_id, customer


def _sync_entitlement(
    session: Session, user_id: str, status: str
) -> None:
    tier = "pro" if status in PRO_STATUSES else "free"
    entitlement = session.get(UserEntitlement, user_id)
    if entitlement is not None and entitlement.source == "manual":
        # Administrator overrides take precedence over provider state.
        return
    reason = f"Stripe subscription status: {status}."
    if entitlement is None:
        if tier == "free":
            return
        entitlement = UserEntitlement(
            user_id=user_id,
            tier="pro",
            limits=None,
            source="stripe",
            granted_by=None,
            reason=reason,
        )
        session.add(entitlement)
    else:
        entitlement.tier = tier
        entitlement.source = "stripe"
        entitlement.granted_by = None
        entitlement.reason = reason


def sync_subscription(session: Session, subscription: Any) -> None:
    subscription_id = subscription.get("id")
    if not isinstance(subscription_id, str) or not subscription_id:
        return
    user_id, customer = _resolve_customer_and_user(session, subscription)
    if user_id is None:
        return

    status = subscription.get("status") or "incomplete"
    trial_start = _dt(subscription.get("trial_start"))
    trial_end = _dt(subscription.get("trial_end"))
    cancel_at = _dt(subscription.get("cancel_at"))
    cancel_at_period_end = bool(
        subscription.get("cancel_at_period_end")
    )
    # Newer Stripe API versions report a scheduled cancellation through
    # ``cancel_at`` even when ``cancel_at_period_end`` is false.
    if cancel_at is not None and cancel_at > _utcnow():
        cancel_at_period_end = True

    record = session.get(StripeSubscription, subscription_id)
    if record is None:
        record = StripeSubscription(
            stripe_subscription_id=subscription_id,
            user_id=user_id,
            stripe_customer_id=subscription.get("customer") or "",
            status=status,
            cancel_at_period_end=cancel_at_period_end,
        )
        session.add(record)
    record.user_id = user_id
    record.stripe_customer_id = subscription.get("customer") or ""
    record.status = status
    record.price_id = _price_id(subscription)
    record.current_period_start = _dt(
        _period_value(subscription, "current_period_start")
    )
    record.current_period_end = _dt(
        _period_value(subscription, "current_period_end")
    )
    record.cancel_at_period_end = cancel_at_period_end
    record.cancel_at = cancel_at
    record.trial_start = trial_start
    record.trial_end = trial_end

    if customer is not None and trial_start is not None:
        if customer.trial_used_at is None:
            customer.trial_used_at = trial_start

    _sync_entitlement(session, user_id, status)


def _sync_checkout_session(session: Session, checkout: Any) -> None:
    customer_id = checkout.get("customer")
    metadata = checkout.get("metadata") or {}
    user_id = checkout.get("client_reference_id") or metadata.get("user_id")
    if not isinstance(customer_id, str) or not isinstance(user_id, str):
        return
    customer = (
        session.query(StripeCustomer)
        .filter(StripeCustomer.stripe_customer_id == customer_id)
        .one_or_none()
    )
    if customer is None:
        session.add(
            StripeCustomer(
                user_id=user_id,
                stripe_customer_id=customer_id,
                email=None,
            )
        )


def _mark_subscription_status(
    session: Session, subscription_id: Any, status: str
) -> None:
    if not isinstance(subscription_id, str):
        return
    record = session.get(StripeSubscription, subscription_id)
    if record is None:
        return
    record.status = status
    _sync_entitlement(session, record.user_id, status)


def _invoice_subscription_id(invoice: Any) -> Any:
    subscription_id = invoice.get("subscription")
    if subscription_id:
        return subscription_id
    parent = invoice.get("parent") or {}
    details = parent.get("subscription_details") or {}
    return details.get("subscription")


def _dispatch_event(session: Session, event_type: str, obj: Any) -> None:
    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        sync_subscription(session, obj)
    elif event_type == "checkout.session.completed":
        _sync_checkout_session(session, obj)
    elif event_type == "invoice.payment_failed":
        _mark_subscription_status(
            session, _invoice_subscription_id(obj), "past_due"
        )
    elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        # Renewal or successful trial conversion. Subscription lifecycle
        # events are authoritative, but this keeps access correct even if a
        # subscription.updated event is delayed.
        _mark_subscription_status(
            session, _invoice_subscription_id(obj), "active"
        )


def process_webhook_event(
    session: Session,
    settings: Settings,
    payload: bytes,
    signature: str | None,
) -> bool:
    """Verify, persist, and process a Stripe event.

    Returns True when the event was processed, False when it was a
    duplicate. Signature failures raise before any state is written.
    """
    if not settings.stripe_webhook_secret:
        raise BillingNotConfiguredError(
            "Stripe billing is not configured."
        )
    if not signature:
        raise WebhookSignatureError("Missing Stripe signature.")

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise WebhookSignatureError("Invalid Stripe webhook signature.") from exc

    event_id = event["id"]
    event_type = event["type"]
    if session.get(StripeWebhookEvent, event_id) is not None:
        return False

    session.add(
        StripeWebhookEvent(event_id=event_id, event_type=event_type)
    )
    try:
        session.flush()
    except IntegrityError:
        # A concurrent delivery of the same event already claimed it.
        session.rollback()
        return False

    try:
        _dispatch_event(
            session, event_type, event["data"]["object"]
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return True
