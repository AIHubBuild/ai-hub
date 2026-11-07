"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError } from "../lib/api";
import { createCheckoutSession } from "../lib/billing";
import { useAuth } from "./auth/auth-provider";

export function UpgradeToProButton({
  className = "ui-button ui-button-primary",
}: {
  className?: string;
}) {
  const { session, loading, configured } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) {
    return <span className="text-sm text-muted">Loading…</span>;
  }

  if (!configured || session === null) {
    return (
      <Link href="/login?redirect=/billing" className={className}>
        Upgrade to Pro
      </Link>
    );
  }

  async function startCheckout() {
    setBusy(true);
    setError(null);
    try {
      const checkout = await createCheckoutSession();
      window.location.assign(checkout.url);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Checkout could not be started.",
      );
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={startCheckout}
        disabled={busy}
        className={className}
      >
        {busy ? "Opening Checkout…" : "Upgrade to Pro"}
      </button>
      {error !== null && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
