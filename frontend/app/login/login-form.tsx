"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { getSupabase } from "../lib/supabase";

type Mode = "sign-in" | "sign-up";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawRedirect = searchParams.get("redirect") ?? "/";
  // Only allow internal paths — never navigate to external origins.
  const redirect =
    rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
      ? rawRedirect
      : "/";

  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const supabase = getSupabase();

  if (supabase === null) {
    return (
      <div
        role="alert"
        className="rounded-2xl bg-surface p-6 text-center ring-1 ring-line/80"
      >
        <h2 className="text-sm font-medium text-ink">
          Supabase is not configured
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
          <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to enable
          authentication.
        </p>
      </div>
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const client = getSupabase();
    if (client === null) {
      return;
    }
    setError(null);
    setNotice(null);
    setSubmitting(true);

    try {
      const { error: authError } =
        mode === "sign-in"
          ? await client.auth.signInWithPassword({ email, password })
          : await client.auth.signUp({ email, password });
      if (authError) {
        setError(authError.message);
        return;
      }
      if (mode === "sign-up") {
        setNotice(
          "Account created. Check your email to confirm your address, then sign in.",
        );
        setMode("sign-in");
        return;
      }
      router.push(redirect);
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl bg-surface p-6 ring-1 ring-line/80 sm:p-7"
    >
      <div className="mb-6 flex rounded-lg bg-surface-muted p-0.5">
        {(["sign-in", "sign-up"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => {
              setMode(option);
              setError(null);
              setNotice(null);
            }}
            aria-pressed={mode === option}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              mode === option
                ? "bg-surface text-ink shadow-sm"
                : "text-muted hover:text-ink"
            }`}
          >
            {option === "sign-in" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <label
        htmlFor="email"
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        Email
      </label>
      <input
        id="email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        className="ui-field"
      />

      <label
        htmlFor="password"
        className="mb-1.5 mt-4 block text-sm font-medium text-ink"
      >
        Password
      </label>
      <input
        id="password"
        type="password"
        required
        minLength={8}
        autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        className="ui-field"
      />

      {error !== null && (
        <p
          role="alert"
          className="mt-4 border-l-2 border-danger bg-surface-muted px-3 py-2 text-sm text-ink-soft"
        >
          {error}
        </p>
      )}
      {notice !== null && (
        <p className="mt-4 border-l-2 border-success bg-surface-muted px-3 py-2 text-sm text-ink-soft">
          {notice}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="ui-button ui-button-primary mt-5 w-full"
      >
        {submitting
          ? "Please wait…"
          : mode === "sign-in"
            ? "Sign in"
            : "Create account"}
      </button>
    </form>
  );
}
