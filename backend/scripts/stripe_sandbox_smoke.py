#!/usr/bin/env python
"""Create a real Stripe sandbox Checkout session for the configured Pro Price.

This uses Stripe TEST mode only. It verifies the configured Price, creates a
temporary user in an in-memory database, creates a Checkout Session through
the same backend service used by the API, and inspects the session's line
item. The session is expired afterwards; no payment is completed.

Usage (from backend/):

    STRIPE_SECRET_KEY=sk_test_... \
    STRIPE_PRICE_ID=price_... \
    STRIPE_PRO_PRICE_CENTS=1900 \
    STRIPE_PRO_PRICE_CURRENCY=eur \
    .venv/bin/python scripts/stripe_sandbox_smoke.py

The Stripe secret key is never printed.
"""

import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stripe  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import AuthUser  # noqa: E402
from app.domains.billing.service import (  # noqa: E402
    create_checkout_session,
    fetch_and_validate_price,
)
from app.models import Base  # noqa: E402

logging.getLogger("stripe").setLevel(logging.WARNING)


def main() -> int:
    settings = get_settings()
    try:
        price = fetch_and_validate_price(settings)
    except Exception as exc:
        print(f"Stripe price verification FAILED: {exc}", file=sys.stderr)
        return 1

    print("Stripe price verification PASSED")
    print(json.dumps(price, indent=2, sort_keys=True))

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    user = AuthUser(
        id=str(uuid4()),
        email=f"stripe-smoke+{uuid4().hex[:8]}@example.com",
        email_verified=True,
    )

    try:
        with session_factory() as session:
            checkout = create_checkout_session(session, user, settings)
        retrieved = stripe.checkout.Session.retrieve(
            checkout["session_id"],
            expand=["line_items.data.price"],
        )
        line_items = retrieved.get("line_items", {}).get("data", [])
        if not line_items:
            raise RuntimeError("Checkout Session has no line items.")
        line_price = line_items[0].get("price") or {}
        if line_price.get("id") != settings.stripe_price_id:
            raise RuntimeError(
                "Checkout Session does not use the configured Price."
            )
        if int(line_price.get("unit_amount") or 0) != int(
            settings.stripe_pro_price_cents
        ):
            raise RuntimeError(
                "Checkout Session Price amount does not match the plan."
            )
        if (line_price.get("currency") or "").lower() != (
            settings.stripe_pro_price_currency.lower()
        ):
            raise RuntimeError(
                "Checkout Session Price currency does not match the plan."
            )
        if not checkout["trial_applied"]:
            raise RuntimeError(
                "Eligible user did not receive the trial."
            )

        print("Checkout sandbox smoke test PASSED")
        print(
            json.dumps(
                {
                    "session_id": checkout["session_id"],
                    "url": checkout["url"],
                    "trial_applied": checkout["trial_applied"],
                    "price_id": line_price.get("id"),
                    "unit_amount": line_price.get("unit_amount"),
                    "currency": line_price.get("currency"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        try:
            stripe.checkout.Session.expire(checkout["session_id"])
        except Exception:
            # Expiring is cleanup only; the assertions above are authoritative.
            pass
        return 0
    except Exception as exc:
        print(f"Checkout sandbox smoke test FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
