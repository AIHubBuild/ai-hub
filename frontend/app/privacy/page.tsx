import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Notice",
  description: "How AI Hub collects, uses, and protects account data.",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <p className="ui-eyebrow">Privacy</p>
      <h1 className="ui-display mt-3 text-4xl text-ink">Privacy Notice</h1>
      <p className="mt-3 text-sm text-muted">Last updated: 19 October 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-7 text-ink-soft">
        <section>
          <h2 className="text-base font-semibold text-ink">
            Information we collect
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Account email and authentication data managed by Supabase Auth.</li>
            <li>
              Profile details you provide: full name, optional phone number,
              optional country, optional city, optional career goal, and
              marketing preference.
            </li>
            <li>
              Content you submit to Resume ATS and AI IT Support Copilot,
              including resumes, job descriptions, conversations, and tickets.
            </li>
            <li>
              Operational metadata such as request status, latency, and error
              category. Passwords are never stored in your profile.
            </li>
            <li>
              Bot-protection signals processed by hCaptcha when you sign in or
              create an account.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            How we use it
          </h2>
          <p className="mt-2">
            We use this information to create and secure your account, provide
            the assistants you request, maintain reliability, respond to
            support issues, and send marketing only when you have opted in.
            Marketing consent is optional and separate from account messages.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Service providers
          </h2>
          <p className="mt-2">
            Supabase provides authentication and database services. OpenAI
            provides AI processing for assistant workflows. hCaptcha provides
            bot-protection challenges on sign-in and sign-up and may process
            browser, device, and interaction signals for that purpose. We do
            not sell personal information. We do not store payment card
            details; any future paid plan must use a trusted payment provider.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Security and retention
          </h2>
          <p className="mt-2">
            Access is restricted by account authentication and database
            policies. Data is retained only as needed to operate the service,
            meet legal obligations, and resolve disputes. Do not include
            secrets or unnecessary sensitive information in resumes, support
            messages, or profile fields.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">
            Your choices
          </h2>
          <p className="mt-2">
            You can update profile information and marketing consent from your
            Profile page. You can request account or data deletion through the
            support channel available in your account.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-ink">Contact</h2>
          <p className="mt-2">
            Privacy questions can be sent through the support channel available
            in your account.
          </p>
        </section>
      </div>
    </main>
  );
}
