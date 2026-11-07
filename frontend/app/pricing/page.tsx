import Link from "next/link";
import { UpgradeToProButton } from "../components/upgrade-to-pro-button";

export const metadata = { title: "Pricing" };

export default function PricingPage() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-12 sm:px-6 lg:px-8">
      <header className="mx-auto max-w-2xl text-center">
        <p className="ui-eyebrow">Pricing</p>
        <h1 className="ui-display mt-3 text-4xl text-ink sm:text-5xl">
          Choose the plan that fits your work.
        </h1>
        <p className="mt-4 text-sm leading-6 text-muted sm:text-base">
          Start with the free tools, or unlock Pro with a 24-hour trial for
          eligible verified accounts.
        </p>
      </header>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        <section className="rounded-3xl border border-line bg-surface p-7">
          <p className="ui-eyebrow">Free</p>
          <p className="ui-display mt-3 text-4xl text-ink">€0</p>
          <p className="mt-2 text-sm text-muted">For getting started.</p>
          <ul className="mt-6 space-y-3 text-sm text-ink-soft">
            <li>Resume upload and ATS analysis</li>
            <li>IT Support Copilot sessions</li>
            <li>Private account workspace</li>
          </ul>
          <Link href="/login" className="ui-button ui-button-secondary mt-8 w-full">
            Start for free
          </Link>
        </section>

        <section className="rounded-3xl border border-accent/30 bg-surface p-7 ring-1 ring-accent/20">
          <div className="flex items-center justify-between gap-3">
            <p className="ui-eyebrow text-accent">Pro</p>
            <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-semibold text-accent">
              24-hour trial
            </span>
          </div>
          <p className="ui-display mt-3 text-4xl text-ink">
            €19<span className="text-base font-medium text-muted">/month</span>
          </p>
          <p className="mt-2 text-sm text-muted">
            Eligible verified users can try Pro free for 24 hours.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-ink-soft">
            <li>Everything in Free</li>
            <li>Pro-only tailored resume downloads</li>
            <li>Pro-only cover letter downloads</li>
            <li>Subscription management in the Stripe Customer Portal</li>
          </ul>
          <div className="mt-8">
            <UpgradeToProButton className="ui-button ui-button-primary w-full" />
          </div>
          <p className="mt-3 text-center text-[11px] leading-5 text-muted">
            Secure recurring billing handled by Stripe. Cancel anytime.
          </p>
        </section>
      </div>
    </main>
  );
}
