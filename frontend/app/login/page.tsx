import { Suspense } from "react";
import { HubMarkIcon } from "../components/icons";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="mx-auto w-full max-w-md flex-1 px-4 py-12 sm:px-6 sm:py-16">
      <section aria-labelledby="login-heading" className="mb-7 text-center">
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-ink text-canvas">
          <HubMarkIcon className="h-5 w-5" />
        </span>
        <h1
          id="login-heading"
          className="ui-display mt-5 text-3xl text-ink"
        >
          Sign in to AI Hub
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          Your analyses, conversations, and tickets stay private to your
          account.
        </p>
      </section>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
