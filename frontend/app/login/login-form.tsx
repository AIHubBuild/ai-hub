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
        className="rounded-xl border border-zinc-200 bg-zinc-50 p-6 text-center dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
          Supabase is not configured
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
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
      className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="mb-5 flex rounded-lg border border-zinc-200 p-0.5 dark:border-zinc-800">
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
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 ${
              mode === option
                ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
            }`}
          >
            {option === "sign-in" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <label
        htmlFor="email"
        className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
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
        className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-2.5 text-sm text-zinc-900 focus:outline-2 focus:outline-offset-2 focus:outline-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50"
      />

      <label
        htmlFor="password"
        className="mb-1.5 mt-4 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
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
        className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-2.5 text-sm text-zinc-900 focus:outline-2 focus:outline-offset-2 focus:outline-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50"
      />

      {error !== null && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400"
        >
          {error}
        </p>
      )}
      {notice !== null && (
        <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-400">
          {notice}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="mt-5 inline-flex w-full items-center justify-center rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
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
