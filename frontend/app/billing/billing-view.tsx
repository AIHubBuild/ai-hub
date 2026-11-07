"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../components/auth/auth-provider";
import { ApiError } from "../lib/api";
import {
  createCheckoutSession,
  createPortalSession,
  fetchBillingStatus,
  type BillingStatusData,
} from "../lib/billing";

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatPrice(cents: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Active",
    trialing: "Free trial",
    past_due: "Payment failed",
    unpaid: "Payment required",
    canceled: "Cancelled",
    incomplete: "Incomplete",
    incomplete_expired: "Expired",
    paused: "Paused",
  };
  return labels[status] ?? status;
}

export function BillingView() {
  const { session, loading: authLoading, configured } = useAuth();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<BillingStatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<"checkout" | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const userId = session?.user.id ?? null;

  useEffect(() => {
    if (!userId) {
      return;
    }
    let active = true;
    const load = async () => {
      await Promise.resolve();
      if (!active) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const next = await fetchBillingStatus();
        if (active) {
          setStatus(next);
        }
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Billing status could not be loaded.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [userId]);

  const queryNotice =
    searchParams.get("checkout") === "success"
      ? "Checkout completed. Your Pro access updates after Stripe confirms the subscription."
      : searchParams.get("checkout") === "cancelled"
        ? "Checkout was cancelled. No charge was made."
        : searchParams.get("portal") === "return"
          ? "Billing details updated."
          : null;
  const visibleNotice = notice ?? queryNotice;

  async function startCheckout() {
    setAction("checkout");
    setError(null);
    setNotice(null);
    try {
      const created = await createCheckoutSession();
      window.location.assign(created.url);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Checkout could not be started.",
      );
    } finally {
      setAction(null);
    }
  }

  async function openPortal() {
    setAction("portal");
    setError(null);
    setNotice(null);
    try {
      const created = await createPortalSession();
      window.location.assign(created.url);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The billing portal could not be opened.",
      );
    } finally {
      setAction(null);
    }
  }

  if (authLoading) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <p className="text-sm text-muted">Loading billing…</p>
      </main>
    );
  }

  if (!configured || session === null) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <section className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
          <p className="ui-eyebrow">Billing</p>
          <h1 className="ui-display mt-3 text-3xl text-ink">
            Sign in to manage billing
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
            Subscription status is private to your account.
          </p>
          <Link
            href="/login?redirect=%2Fbilling"
            className="ui-button ui-button-primary mt-5"
          >
            Sign in
          </Link>
        </section>
      </main>
    );
  }

  const subscription = status?.subscription ?? null;
  const isPro = status?.is_pro === true;
  const trialEligible = status?.trial_eligible === true;
  const cancellationScheduled =
    subscription !== null &&
    (subscription.cancel_at_period_end || subscription.cancel_at !== null);
  const accessUntil =
    subscription?.cancel_at ?? subscription?.current_period_end ?? null;
  const priceLabel =
    status === null
      ? null
      : formatPrice(status.price_cents, status.price_currency);
  const trialLabel =
    status === null ? "24-hour" : `${status.trial_hours}-hour`;

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6 sm:py-12">
      <header className="border-b border-line pb-6">
        <p className="ui-eyebrow">Subscription</p>
        <h1 className="ui-display mt-3 text-3xl text-ink">Billing</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          AI Hub Pro includes a {trialLabel} free trial for eligible verified
          accounts. The current monthly price is shown below.
        </p>
      </header>

      {loading ? (
        <p className="mt-6 text-sm text-muted">Loading billing status…</p>
      ) : status === null ? (
        <div className="mt-6 rounded-xl border-l-2 border-danger bg-surface p-4 text-sm text-ink-soft">
          <p>{error ?? "Billing status is unavailable."}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="ui-button ui-button-secondary mt-3"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          <section className="rounded-2xl bg-surface p-6 ring-1 ring-line/80">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="ui-eyebrow">Current plan</p>
                <h2 className="ui-display mt-2 text-2xl text-ink">
                  {isPro ? "AI Hub Pro" : "Free"}
                </h2>
                <p className="mt-1 text-sm text-ink-soft">
                  {isPro
                    ? "Pro features are enabled for this account."
                    : `Upgrade for ${priceLabel ?? "the configured price"} per month to unlock Pro-only downloads and features.`}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  isPro
                    ? "bg-accent-soft text-accent"
                    : "bg-surface-muted text-muted"
                }`}
              >
                {isPro ? "Pro" : "Free"}
              </span>
            </div>

            {subscription !== null && (
              <dl className="mt-5 grid gap-3 border-t border-line pt-5 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                    Status
                  </dt>
                  <dd className="mt-1 text-ink-soft">
                    {statusLabel(subscription.status)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                    {cancellationScheduled ? "Access until" : "Renews"}
                  </dt>
                  <dd className="mt-1 text-ink-soft">
                    {formatDate(
                      cancellationScheduled
                        ? accessUntil
                        : subscription.current_period_end,
                    )}
                  </dd>
                </div>
                {subscription.trial_start !== null && (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                      Trial started
                    </dt>
                    <dd className="mt-1 text-ink-soft">
                      {formatDate(subscription.trial_start)}
                    </dd>
                  </div>
                )}
                {subscription.trial_end !== null && (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                      Trial ends
                    </dt>
                    <dd className="mt-1 text-ink-soft">
                      {formatDate(subscription.trial_end)}
                    </dd>
                  </div>
                )}
                {cancellationScheduled && (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                      Cancellation
                    </dt>
                    <dd className="mt-1 text-ink-soft">Scheduled</dd>
                  </div>
                )}
              </dl>
            )}

            {subscription?.status === "past_due" && (
              <p
                role="alert"
                className="mt-4 border-l-2 border-danger bg-surface-muted px-3 py-2 text-sm text-ink-soft"
              >
                The last payment failed. Update your payment method in the
                billing portal to restore Pro access.
              </p>
            )}

            <div className="mt-5 flex flex-wrap gap-3 border-t border-line pt-5">
              {!isPro && (
                <button
                  type="button"
                  onClick={startCheckout}
                  disabled={action !== null}
                  className="ui-button ui-button-primary"
                >
                  {action === "checkout"
                    ? "Opening Checkout…"
                    : trialEligible
                      ? `Start ${trialLabel} free trial`
                      : `Subscribe for ${priceLabel ?? "Pro"}/month`}
                </button>
              )}
              <button
                type="button"
                onClick={openPortal}
                disabled={action !== null || !status.has_billing_account}
                className="ui-button ui-button-secondary"
              >
                {action === "portal"
                  ? "Opening portal…"
                  : "Manage billing"}
              </button>
            </div>
            {!isPro && trialEligible && priceLabel !== null && (
              <p className="mt-2 text-xs text-muted">
                After the {trialLabel} trial: {priceLabel}/month. Cancel
                anytime in the billing portal.
              </p>
            )}
            {!status.has_billing_account && (
              <p className="mt-2 text-xs text-muted">
                A billing account is created when you start Checkout.
              </p>
            )}
          </section>

          {visibleNotice !== null && (
            <p className="border-l-2 border-success bg-surface-muted px-3 py-2 text-sm text-ink-soft">
              {visibleNotice}
            </p>
          )}
          {error !== null && (
            <p
              role="alert"
              className="border-l-2 border-danger bg-surface-muted px-3 py-2 text-sm text-ink-soft"
            >
              {error}
            </p>
          )}
        </div>
      )}
    </main>
  );
}
