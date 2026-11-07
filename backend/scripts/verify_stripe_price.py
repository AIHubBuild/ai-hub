#!/usr/bin/env python
"""Verify the configured Stripe Pro Price against the sandbox account.

Usage (from backend/):

    STRIPE_SECRET_KEY=sk_test_... \
    STRIPE_PRICE_ID=price_... \
    STRIPE_PRO_PRICE_CENTS=1900 \
    STRIPE_PRO_PRICE_CURRENCY=eur \
    .venv/bin/python scripts/verify_stripe_price.py

Exits non-zero when the Price does not match the configured Pro plan.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.domains.billing.service import fetch_and_validate_price  # noqa: E402

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
