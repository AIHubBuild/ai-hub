#!/usr/bin/env python
"""End-to-end Stripe sandbox integration test.

Requires a Stripe TEST secret key in the backend environment. It performs
real Stripe sandbox API calls and cleans up afterwards:

- verifies the configured Pro Price (EUR 19/month)
- creates a Checkout Session and verifies its Price and trial
- creates a real trialing subscription with a Stripe test payment method
- syncs the subscription into the local entitlement tables
- creates a real Customer Portal session
- posts signed Stripe webhook events to the real FastAPI route
- verifies idempotency, Pro grant, cancellation downgrade, and cleanup

Secrets are never printed.
"""

import hashlib
import hmac
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stripe  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.security import AuthUser  # noqa: E402
from app.domains.billing.service import (  # noqa: E402
    create_checkout_session,
    create_portal_session,
    fetch_and_validate_price,
    sync_subscription,
)
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.admin import UserEntitlement  # noqa: E402
from app.models.billing import (  # noqa: E402
    StripeCustomer,
    StripeSubscription,
)


logging.getLogger("stripe").setLevel(logging.WARNING)


def plain(value):
    return json.loads(json.dumps(value))


def sign(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(
        secret.encode(), signed, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def send_event(client: TestClient, event: dict, secret: str):
    payload = json.dumps(event).encode()
    return client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={
            "stripe-signature": sign(payload, secret),
            "content-type": "application/json",
        },
    )


def main() -> int:
    settings = get_settings()
    if not settings.stripe_secret_key:
        print("STRIPE_SECRET_KEY is not configured.", file=sys.stderr)
        return 1

    customer_id = None
    subscription_id = None
    checkout_id = None
    webhook_db = (
        Path(tempfile.gettempdir())
        / f"aihub-stripe-webhook-{uuid4().hex}.db"
    )
    try:
        price = fetch_and_validate_price(settings)
        print("1. Price verification PASSED")
        print(json.dumps(price, indent=2, sort_keys=True))

        user = AuthUser(
            id=str(uuid4()),
            email=f"stripe-integration+{uuid4().hex[:8]}@example.com",
            email_verified=True,
        )

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(
            bind=engine, expire_on_commit=False
        )

        customer = stripe.Customer.create(
            email=user.email, metadata={"user_id": user.id}
        )
        customer_id = customer["id"]
        with session_factory() as session:
            session.add(
                StripeCustomer(
                    user_id=user.id,
                    stripe_customer_id=customer_id,
                    email=user.email,
                )
            )
            session.commit()

        with session_factory() as session:
            checkout = create_checkout_session(session, user, settings)
        checkout_id = checkout["session_id"]
        retrieved = stripe.checkout.Session.retrieve(
            checkout_id, expand=["line_items.data.price"]
        )
        line_items = retrieved.get("line_items", {}).get("data", [])
        line_price = (line_items[0].get("price") if line_items else {}) or {}
        assert line_price.get("id") == settings.stripe_price_id
        assert int(line_price.get("unit_amount") or 0) == int(
            settings.stripe_pro_price_cents
        )
        assert (line_price.get("currency") or "").lower() == (
            settings.stripe_pro_price_currency.lower()
        )
        assert checkout["trial_applied"] is True
        print("2. Checkout Session verification PASSED")
        print(
            json.dumps(
                {
                    "session_id": checkout_id,
                    "trial_applied": checkout["trial_applied"],
                    "price_id": line_price.get("id"),
                    "unit_amount": line_price.get("unit_amount"),
                    "currency": line_price.get("currency"),
                },
                indent=2,
                sort_keys=True,
            )
        )

        payment_method = stripe.PaymentMethod.attach(
            "pm_card_visa", customer=customer_id
        )
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": settings.stripe_price_id}],
            trial_period_days=1,
            default_payment_method=payment_method["id"],
            metadata={"user_id": user.id},
        )
        subscription_id = subscription["id"]
        with session_factory() as session:
            sync_subscription(session, subscription)
            session.commit()
            record = session.get(StripeSubscription, subscription_id)
            entitlement = session.get(UserEntitlement, user.id)
            assert record is not None
            assert record.status == "trialing"
            assert record.trial_end is not None
            assert entitlement is not None
            assert entitlement.tier == "pro"
            assert entitlement.source == "stripe"
        print("3. Subscription sync and Pro entitlement PASSED")

        with session_factory() as session:
            portal = create_portal_session(session, user, settings)
        assert portal["url"].startswith("https://")
        print("4. Customer Portal session PASSED")

        webhook_secret = "whsec_integration_" + uuid4().hex
        webhook_app = create_app(
            Settings(
                _env_file=None,
                environment="test",
                ai_deployment=False,
                database_url=f"sqlite:///{webhook_db}",
                supabase_jwt_secret="integration-test-secret",
                stripe_secret_key=settings.stripe_secret_key,
                stripe_price_id=settings.stripe_price_id,
                stripe_pro_price_cents=settings.stripe_pro_price_cents,
                stripe_pro_price_currency=settings.stripe_pro_price_currency,
                stripe_webhook_secret=webhook_secret,
            )
        )
        Base.metadata.create_all(webhook_app.state.engine)
        webhook_client = TestClient(webhook_app)

        subscription_data = plain(subscription)
        event = {
            "id": f"evt_integration_{uuid4().hex}",
            "type": "customer.subscription.updated",
            "data": {"object": subscription_data},
        }
        response = send_event(webhook_client, event, webhook_secret)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["duplicate"] is False
        duplicate = send_event(webhook_client, event, webhook_secret)
        assert duplicate.status_code == 200
        assert duplicate.json()["data"]["duplicate"] is True
        with webhook_app.state.session_factory() as session:
            record = session.get(StripeSubscription, subscription_id)
            entitlement = session.get(UserEntitlement, user.id)
            assert record is not None
            assert record.status == "trialing"
            assert entitlement is not None
            assert entitlement.tier == "pro"
        print("5. Signed webhook idempotency and sync PASSED")

        cancelled = stripe.Subscription.delete(subscription_id)
        subscription_id = None
        cancelled_data = plain(cancelled)
        cancelled_event = {
            "id": f"evt_integration_{uuid4().hex}",
            "type": "customer.subscription.deleted",
            "data": {"object": cancelled_data},
        }
        response = send_event(
            webhook_client, cancelled_event, webhook_secret
        )
        assert response.status_code == 200, response.text
        with webhook_app.state.session_factory() as session:
            record = session.get(
                StripeSubscription, cancelled_data["id"]
            )
            entitlement = session.get(UserEntitlement, user.id)
            assert record is not None
            assert record.status == "canceled"
            assert entitlement is not None
            assert entitlement.tier == "free"
        print("6. Cancellation downgrade PASSED")

        print("STRIPE SANDBOX INTEGRATION TEST PASSED")
        return 0
    except Exception as exc:
        print(f"STRIPE SANDBOX INTEGRATION TEST FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if checkout_id:
            try:
                stripe.checkout.Session.expire(checkout_id)
            except Exception:
                pass
        if subscription_id:
            try:
                stripe.Subscription.delete(subscription_id)
            except Exception:
                pass
        if customer_id:
            try:
                stripe.Customer.delete(customer_id)
            except Exception:
                pass
        try:
            webhook_db.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
