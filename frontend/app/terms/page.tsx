import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms governing use of AI Hub.",
};

export default function TermsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <p className="ui-eyebrow">Legal</p>
      <h1 className="ui-display mt-3 text-4xl text-ink">Terms of Service</h1>
      <p className="mt-3 text-sm text-muted">Last updated: 19 October 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-7 text-ink-soft">
        <section>
          <h2 className="text-base font-semibold text-ink">
            Using AI Hub
          </h2>
          <p className="mt-2">
            You must provide accurate account information, keep your login
            credentials secure, and use AI Hub only for lawful purposes. You
            are responsible for activity performed through your account.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            AI-generated output
          </h2>
          <p className="mt-2">
            Resume analysis, support guidance, and other AI-assisted output may
            be incomplete or inaccurate. You must review output before relying
            on it for employment, legal, financial, or other important
            decisions.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Your content
          </h2>
          <p className="mt-2">
            You retain responsibility for resumes, job descriptions, support
            conversations, and other content you submit. Do not upload content
            you do not have permission to use, and do not include unnecessary
            sensitive personal information.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Availability and changes
          </h2>
          <p className="mt-2">
            Features may change, be suspended, or be discontinued. We may
            update these terms as the service evolves. Continued use after an
            update means you accept the revised terms.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Account termination
          </h2>
          <p className="mt-2">
            You may stop using the service at any time. Accounts that violate
            these terms or create security risks may be restricted or
            suspended.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">Contact</h2>
          <p className="mt-2">
            Questions about these terms can be sent through the support channel
            available in your account.
          </p>
        </section>
      </div>
    </main>
  );
}
