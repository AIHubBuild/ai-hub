import { Suspense } from "react";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="mx-auto w-full max-w-md flex-1 px-6 py-16">
      <section aria-labelledby="login-heading" className="mb-8 text-center">
        <h1
          id="login-heading"
          className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          Sign in to AI Hub
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Your resume analyses and documents are private to your account.
        </p>
      </section>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
