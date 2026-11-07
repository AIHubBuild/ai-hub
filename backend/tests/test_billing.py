"""Stripe billing, webhook, and Pro-entitlement tests.

No live Stripe network calls are made: Stripe SDK create methods are
patched with local fakes, and webhook signatures are computed locally.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import jwt
import pytest
import stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domains.billing.service import (
    PriceVerificationError,
    validate_price_object,
)
from app.main import create_app
from app.models import Base
from app.models.admin import UserEntitlement
from app.models.billing import StripeCustomer, StripeSubscription
from app.models.profile import UserProfile

TEST_SECRET = "test-billing-secret-0123456789abcdef0123456789"
WEBHOOK_SECRET = "whsec_test_billing_secret"
USER_ID = "550e8400-e29b-41d4-a716-446655440020"
OTHER_USER_ID = "660e8400-e29b-41d4-a716-446655440021"
SUB_UUID = "770e8400-e29b-41d4-a716-446655440022"


def make_token(
    user_id: str = USER_ID,
    *,
    email_verified: bool = True,
) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": "billing@example.com",
            "email_verified": email_verified,
            "exp": int(time.time()) + 3600,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def auth_headers(
    user_id: str = USER_ID, *, email_verified: bool = True
) -> dict:
    return {
        "Authorization": (
            f"Bearer {make_token(user_id, email_verified=email_verified)}"
        )
    }


def build_app(tmp_path, **overrides) -> FastAPI:
    settings = {
        "database_url": f"sqlite:///{tmp_path / 'billing.db'}",
        "supabase_jwt_secret": TEST_SECRET,
        "frontend_url": "https://app.example.test",
        "stripe_secret_key": "sk_test_local",
        "stripe_webhook_secret": WEBHOOK_SECRET,
        "stripe_price_id": "price_pro_test",
        "stripe_pro_price_cents": 1900,
        "stripe_pro_price_currency": "eur",
        "stripe_trial_hours": 24,
    }
    settings.update(overrides)
    app = create_app(Settings(_env_file=None, **settings))
    Base.metadata.create_all(app.state.engine)
    now = datetime.now(timezone.utc)
    with app.state.session_factory() as session:
        for user_id in (USER_ID, OTHER_USER_ID):
            session.add(
                UserProfile(
                    user_id=user_id,
                    full_name="Billing Test User",
                    terms_accepted_at=now,
                    terms_version="test",
                    privacy_accepted_at=now,
                    privacy_version="test",
                )
            )
        session.commit()
    return app


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_stripe_price(monkeypatch):
    def fake_retrieve(price_id):
        return {
            "id": price_id,
            "active": True,
            "type": "recurring",
            "unit_amount": 1900,
            "currency": "eur",
            "recurring": {"interval": "month", "interval_count": 1},
        }

    monkeypatch.setattr(
        stripe.Price, "retrieve", staticmethod(fake_retrieve)
    )


def sign_payload(payload: bytes) -> str:
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), signed, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def subscription_event(
    event_id: str,
    *,
    status: str,
    event_type: str = "customer.subscription.updated",
    user_id: str = USER_ID,
    trial_start: int | None = None,
    cancel_at: int | None = None,
) -> dict:
    now = int(time.time())
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_test_1",
                "customer": "cus_test_1",
                "status": status,
                "metadata": {"user_id": user_id},
                "items": {
                    "data": [
                        {
                            "price": {"id": "price_pro_test"},
                            "current_period_start": now,
                            "current_period_end": now + 30 * 86400,
                        }
                    ]
                },
                "cancel_at_period_end": False,
                "cancel_at": cancel_at,
                "trial_start": trial_start,
                "trial_end": (
                    trial_start + 86400 if trial_start is not None else None
                ),
            }
        },
    }


def send_webhook(client, event: dict):
    payload = json.dumps(event).encode()
    return client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={
            "stripe-signature": sign_payload(payload),
            "content-type": "application/json",
        },
    )


def test_billing_status_requires_authentication(client):
    assert client.get("/api/v1/billing/status").status_code == 401
    assert client.post("/api/v1/billing/checkout").status_code == 401
    assert client.post("/api/v1/billing/portal").status_code == 401


def test_billing_status_defaults_to_free(client):
    response = client.get(
        "/api/v1/billing/status", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tier"] == "free"
    assert data["is_pro"] is False
    assert data["trial_eligible"] is True
    assert data["has_billing_account"] is False
    assert data["price_cents"] == 1900
    assert data["price_currency"] == "eur"
    assert data["trial_hours"] == 24
    assert data["subscription"] is None


def test_price_validation_accepts_configured_19_eur_monthly(app):
    price = {
        "id": "price_pro_test",
        "active": True,
        "type": "recurring",
        "unit_amount": 1900,
        "currency": "eur",
        "recurring": {"interval": "month", "interval_count": 1},
    }
    result = validate_price_object(price, app.state.settings)
    assert result["unit_amount"] == 1900
    assert result["currency"] == "eur"
    assert result["interval"] == "month"


@pytest.mark.parametrize(
    "overrides",
    [
        {"unit_amount": 900},
        {"currency": "usd"},
        {"type": "one_time", "recurring": None},
        {"recurring": {"interval": "year", "interval_count": 1}},
        {"active": False},
    ],
)
def test_price_validation_rejects_wrong_plan(app, overrides):
    price = {
        "id": "price_pro_test",
        "active": True,
        "type": "recurring",
        "unit_amount": 1900,
        "currency": "eur",
        "recurring": {"interval": "month", "interval_count": 1},
    }
    price.update(overrides)
    with pytest.raises(PriceVerificationError):
        validate_price_object(price, app.state.settings)


def test_checkout_requires_verified_email(client):
    response = client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(email_verified=False),
    )
    assert response.status_code == 403
    assert response.json()["message"] == "Email verification is required."


def test_checkout_fails_closed_without_configuration(tmp_path):
    app = build_app(
        tmp_path,
        stripe_secret_key="",
        stripe_price_id="",
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/checkout", headers=auth_headers()
    )
    assert response.status_code == 503


def test_checkout_rejects_price_that_does_not_match_plan(
    client, monkeypatch
):
    monkeypatch.setattr(
        stripe.Price,
        "retrieve",
        staticmethod(
            lambda price_id: {
                "id": price_id,
                "active": True,
                "type": "recurring",
                "unit_amount": 900,
                "currency": "eur",
                "recurring": {"interval": "month", "interval_count": 1},
            }
        ),
    )
    response = client.post(
        "/api/v1/billing/checkout", headers=auth_headers()
    )
    assert response.status_code == 503
    assert response.json()["message"] == (
        "Stripe price configuration is invalid."
    )


def test_checkout_creates_trial_once(app, client, monkeypatch):
    customer_calls: list[dict] = []
    checkout_calls: list[dict] = []

    def fake_customer_create(**kwargs):
        customer_calls.append(kwargs)
        return {"id": "cus_test_1"}

    def fake_checkout_create(**kwargs):
        checkout_calls.append(kwargs)
        return {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.test/cs_test_1",
        }

    monkeypatch.setattr(
        stripe.Customer, "create", staticmethod(fake_customer_create)
    )
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        staticmethod(fake_checkout_create),
    )

    first = client.post(
        "/api/v1/billing/checkout", headers=auth_headers()
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["trial_applied"] is True
    assert first_data["url"].startswith("https://checkout.stripe.test/")
    assert checkout_calls[0]["subscription_data"]["trial_period_days"] == 1
    assert checkout_calls[0]["client_reference_id"] == USER_ID
    assert checkout_calls[0]["line_items"] == [
        {"price": "price_pro_test", "quantity": 1}
    ]

    with app.state.session_factory() as session:
        customer = session.get(StripeCustomer, USER_ID)
        assert customer is not None
        assert customer.stripe_customer_id == "cus_test_1"
        assert customer.trial_used_at is not None

    second = client.post(
        "/api/v1/billing/checkout", headers=auth_headers()
    )
    assert second.status_code == 200
    assert second.json()["data"]["trial_applied"] is False
    assert "trial_period_days" not in checkout_calls[1]["subscription_data"]
    assert customer_calls and len(customer_calls) == 1


def test_checkout_blocks_existing_active_subscription(app, client, monkeypatch):
    monkeypatch.setattr(
        stripe.Customer,
        "create",
        staticmethod(lambda **kwargs: {"id": "cus_test_1"}),
    )
    with app.state.session_factory() as session:
        session.add(
            StripeCustomer(
                user_id=USER_ID,
                stripe_customer_id="cus_test_1",
                email="billing@example.com",
            )
        )
        session.add(
            StripeSubscription(
                stripe_subscription_id="sub_existing",
                user_id=USER_ID,
                stripe_customer_id="cus_test_1",
                status="active",
                cancel_at_period_end=False,
            )
        )
        session.commit()

    response = client.post(
        "/api/v1/billing/checkout", headers=auth_headers()
    )
    assert response.status_code == 409


def test_portal_requires_existing_customer(app, client, monkeypatch):
    missing = client.post(
        "/api/v1/billing/portal", headers=auth_headers()
    )
    assert missing.status_code == 409

    monkeypatch.setattr(
        stripe.Customer,
        "create",
        staticmethod(lambda **kwargs: {"id": "cus_test_1"}),
    )
    with app.state.session_factory() as session:
        session.add(
            StripeCustomer(
                user_id=USER_ID,
                stripe_customer_id="cus_test_1",
                email="billing@example.com",
            )
        )
        session.commit()

    calls: list[dict] = []

    def fake_portal_create(**kwargs):
        calls.append(kwargs)
        return {"url": "https://billing.stripe.test/portal"}

    monkeypatch.setattr(
        stripe.billing_portal.Session,
        "create",
        staticmethod(fake_portal_create),
    )
    response = client.post(
        "/api/v1/billing/portal", headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["data"]["url"] == (
        "https://billing.stripe.test/portal"
    )
    assert calls[0]["customer"] == "cus_test_1"


def test_webhook_rejects_invalid_signature(client):
    response = client.post(
        "/api/v1/billing/webhook",
        content=b'{"id":"evt_bad","type":"customer.subscription.updated"}',
        headers={
            "stripe-signature": "t=1,v1=deadbeef",
            "content-type": "application/json",
        },
    )
    assert response.status_code == 400


def test_webhook_updates_subscription_and_entitlement_idempotently(
    app, client
):
    event = subscription_event("evt_active", status="active")
    first = send_webhook(client, event)
    assert first.status_code == 200
    assert first.json()["data"]["duplicate"] is False

    with app.state.session_factory() as session:
        subscription = session.get(StripeSubscription, "sub_test_1")
        assert subscription is not None
        assert subscription.status == "active"
        assert subscription.price_id == "price_pro_test"
        assert subscription.current_period_end is not None
        entitlement = session.get(UserEntitlement, USER_ID)
        assert entitlement is not None
        assert entitlement.tier == "pro"
        assert entitlement.source == "stripe"
        assert entitlement.granted_by is None

    duplicate = send_webhook(client, event)
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True

    with app.state.session_factory() as session:
        assert (
            session.query(StripeSubscription)
            .filter(StripeSubscription.stripe_subscription_id == "sub_test_1")
            .count()
            == 1
        )


def test_webhook_cancellation_downgrades_to_free(app, client):
    send_webhook(
        client, subscription_event("evt_active", status="active")
    )
    cancelled = subscription_event(
        "evt_cancelled",
        status="canceled",
        event_type="customer.subscription.deleted",
    )
    response = send_webhook(client, cancelled)
    assert response.status_code == 200

    with app.state.session_factory() as session:
        assert (
            session.get(StripeSubscription, "sub_test_1").status
            == "canceled"
        )
        entitlement = session.get(UserEntitlement, USER_ID)
        assert entitlement is not None
        assert entitlement.tier == "free"
        assert entitlement.source == "stripe"


def test_webhook_payment_failure_marks_past_due_and_revokes_pro(app, client):
    send_webhook(
        client, subscription_event("evt_active", status="active")
    )
    payload = {
        "id": "evt_payment_failed",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test_1",
                "subscription": "sub_test_1",
                "customer": "cus_test_1",
            }
        },
    }
    response = send_webhook(client, payload)
    assert response.status_code == 200

    with app.state.session_factory() as session:
        assert (
            session.get(StripeSubscription, "sub_test_1").status
            == "past_due"
        )
        assert session.get(UserEntitlement, USER_ID).tier == "free"


def test_webhook_successful_renewal_restores_pro(app, client):
    send_webhook(
        client, subscription_event("evt_active", status="active")
    )
    send_webhook(
        client,
        {
            "id": "evt_payment_failed",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_test_1",
                    "subscription": "sub_test_1",
                }
            },
        },
    )
    response = send_webhook(
        client,
        {
            "id": "evt_invoice_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test_2",
                    "parent": {
                        "subscription_details": {
                            "subscription": "sub_test_1"
                        }
                    },
                }
            },
        },
    )
    assert response.status_code == 200

    with app.state.session_factory() as session:
        assert (
            session.get(StripeSubscription, "sub_test_1").status
            == "active"
        )
        assert session.get(UserEntitlement, USER_ID).tier == "pro"


def test_trial_conversion_to_active_keeps_pro(app, client):
    now = int(time.time())
    send_webhook(
        client,
        subscription_event(
            "evt_trial", status="trialing", trial_start=now
        ),
    )
    assert send_webhook(
        client,
        subscription_event("evt_trial_converted", status="active"),
    ).status_code == 200

    with app.state.session_factory() as session:
        assert (
            session.get(StripeSubscription, "sub_test_1").status == "active"
        )
        assert session.get(UserEntitlement, USER_ID).tier == "pro"


def test_webhook_cancel_at_marks_cancellation_scheduled(app, client):
    now = int(time.time())
    response = send_webhook(
        client,
        subscription_event(
            "evt_cancel_at",
            status="trialing",
            trial_start=now,
            cancel_at=now + 86400,
        ),
    )
    assert response.status_code == 200

    with app.state.session_factory() as session:
        subscription = session.get(StripeSubscription, "sub_test_1")
        assert subscription.cancel_at is not None
        assert subscription.cancel_at_period_end is True
        assert session.get(UserEntitlement, USER_ID).tier == "pro"

    status = client.get(
        "/api/v1/billing/status", headers=auth_headers()
    ).json()["data"]
    assert status["subscription"]["cancel_at"] is not None
    assert status["subscription"]["cancel_at_period_end"] is True


def test_manual_entitlement_is_not_overwritten_by_webhooks(app, client):
    with app.state.session_factory() as session:
        session.add(
            UserEntitlement(
                user_id=USER_ID,
                tier="pro",
                source="manual",
                granted_by=OTHER_USER_ID,
                reason="administrator grant",
            )
        )
        session.commit()

    send_webhook(
        client, subscription_event("evt_active", status="active")
    )
    send_webhook(
        client,
        subscription_event(
            "evt_cancelled",
            status="canceled",
            event_type="customer.subscription.deleted",
        ),
    )

    with app.state.session_factory() as session:
        entitlement = session.get(UserEntitlement, USER_ID)
        assert entitlement.tier == "pro"
        assert entitlement.source == "manual"


def test_trial_subscription_grants_pro_and_records_trial(app, client):
    now = int(time.time())
    response = send_webhook(
        client,
        subscription_event(
            "evt_trial", status="trialing", trial_start=now
        ),
    )
    assert response.status_code == 200

    with app.state.session_factory() as session:
        assert session.get(UserEntitlement, USER_ID).tier == "pro"
        subscription = session.get(StripeSubscription, "sub_test_1")
        assert subscription.trial_start is not None
        assert subscription.trial_end is not None
        customer = session.get(StripeCustomer, USER_ID)
        assert customer.trial_used_at is not None

    status = client.get(
        "/api/v1/billing/status", headers=auth_headers()
    )
    summary = status.json()["data"]["subscription"]
    assert summary["trial_start"] is not None
    assert summary["trial_end"] is not None


def test_docx_download_allowed_during_active_trial(app, client):
    now = int(time.time())
    send_webhook(
        client,
        subscription_event(
            "evt_download_trial", status="trialing", trial_start=now
        ),
    )
    for path in (
        f"/api/v1/analyses/{SUB_UUID}/tailored-resume.docx",
        f"/api/v1/analyses/{SUB_UUID}/tailored-cover-letter.docx",
    ):
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 404


def test_docx_download_blocked_after_trial_expires_without_conversion(
    app, client
):
    now = int(time.time())
    send_webhook(
        client,
        subscription_event(
            "evt_download_trial_expired",
            status="trialing",
            trial_start=now,
        ),
    )
    send_webhook(
        client,
        subscription_event(
            "evt_download_trial_unpaid",
            status="unpaid",
            event_type="customer.subscription.updated",
        ),
    )
    response = client.get(
        f"/api/v1/analyses/{SUB_UUID}/tailored-resume.docx",
        headers=auth_headers(),
    )
    assert response.status_code == 403
    assert response.json()["message"] == (
        "A Pro subscription is required for this feature."
    )


def test_docx_download_allowed_for_active_paid_subscription(app, client):
    send_webhook(
        client,
        subscription_event("evt_download_active_paid", status="active"),
    )
    for path in (
        f"/api/v1/analyses/{SUB_UUID}/tailored-resume.docx",
        f"/api/v1/analyses/{SUB_UUID}/tailored-cover-letter.docx",
    ):
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 404


def test_pro_only_download_rejects_free_users(client):
    response = client.get(
        f"/api/v1/analyses/{SUB_UUID}/tailored-resume.docx",
        headers=auth_headers(),
    )
    assert response.status_code == 403
    assert response.json()["message"] == (
        "A Pro subscription is required for this feature."
    )


def test_pro_only_download_allows_pro_users(client):
    with client.app.state.session_factory() as session:
        session.add(
            UserEntitlement(
                user_id=USER_ID,
                tier="pro",
                source="manual",
                granted_by=OTHER_USER_ID,
                reason="test grant",
            )
        )
        session.commit()

    response = client.get(
        f"/api/v1/analyses/{SUB_UUID}/tailored-resume.docx",
        headers=auth_headers(),
    )
    # Authorization passed; the missing analysis is the only remaining error.
    assert response.status_code == 404
