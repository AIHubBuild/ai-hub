"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "../lib/api";
import { fetchBillingStatus, type BillingStatusData } from "../lib/billing";
import { useAuth } from "./auth/auth-provider";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function PlanStatusCard() {
  const { session, loading: authLoading, configured } = useAuth();
  const [status, setStatus] = useState<BillingStatusData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    let active = true;
    const load = async () => {
      await Promise.resolve();
      try {
        const next = await fetchBillingStatus();
        if (active) setStatus(next);
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Billing status is unavailable.",
          );
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [session]);

  if (authLoading || !configured) {
    return null;
  }

  if (session === null) {
    return (
      <div className="rounded-2xl border border-line bg-surface p-5 sm:flex sm:items-center sm:justify-between sm:gap-6">
        <div>
          <p className="ui-eyebrow">Plan</p>
          <p className="mt-1 text-sm leading-6 text-muted">
            Create an account to start a 24-hour Pro trial.
          </p>
        </div>
        <Link href="/login?redirect=/billing" className="ui-button ui-button-primary mt-3 sm:mt-0">
          Get started
        </Link>
      </div>
    );
  }

  const subscription = status?.subscription ?? null;
  const isPro = status?.is_pro === true;
  const cancellationScheduled =
    subscription !== null &&
    (subscription.cancel_at_period_end || subscription.cancel_at !== null);

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 sm:flex sm:items-center sm:justify-between sm:gap-6">
      <div>
        <p className="ui-eyebrow">Your plan</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className="text-lg font-semibold text-ink">
            {isPro ? "AI Hub Pro" : "Free"}
          </span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
              isPro ? "bg-accent-soft text-accent" : "bg-surface-muted text-muted"
            }`}
          >
            {isPro ? "Pro" : "Free"}
          </span>
        </div>
        <p className="mt-1 text-sm leading-6 text-muted">
          {status === null
            ? error ?? "Loading subscription status…"
            : isPro
              ? cancellationScheduled
                ? `Pro access until ${formatDate(subscription?.cancel_at ?? subscription?.current_period_end ?? null)}.`
                : subscription?.trial_end
                  ? `Pro trial ends ${formatDate(subscription.trial_end)}.`
                  : "Pro features are enabled."
              : "Upgrade for €19/month to unlock Pro features."}
        </p>
      </div>
      <Link href="/billing" className="ui-button ui-button-secondary mt-3 shrink-0 sm:mt-0">
        {isPro ? "Manage billing" : "View plans"}
      </Link>
    </div>
  );
}
