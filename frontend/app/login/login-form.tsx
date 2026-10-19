"use client";

import HCaptcha from "@hcaptcha/react-hcaptcha";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { getSupabase } from "../lib/supabase";

type Mode = "sign-in" | "sign-up";

const HCAPTCHA_SITE_KEY = (
  process.env.NEXT_PUBLIC_HCAPTCHA_SITE_KEY ?? ""
).trim();

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
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState<string | null>(null);
  const captchaRef = useRef<HCaptcha>(null);

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

  function resetCaptcha() {
    captchaRef.current?.resetCaptcha();
    setCaptchaToken(null);
  }

  function validateCaptcha(): string | null {
    if (!HCAPTCHA_SITE_KEY) {
      return "hCaptcha is not configured. Set NEXT_PUBLIC_HCAPTCHA_SITE_KEY and rebuild the frontend.";
    }
    if (captchaToken === null) {
      return "Complete the CAPTCHA before continuing.";
    }
    return null;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const client = getSupabase();
    if (client === null) {
      return;
    }
    setError(null);
    setNotice(null);

    const captchaValidationError = validateCaptcha();
    if (captchaValidationError !== null) {
      setError(captchaValidationError);
      return;
    }
    const token = captchaToken;
    if (token === null) {
      setError("Complete the CAPTCHA before continuing.");
      return;
    }
    setSubmitting(true);

    try {
      const { error: authError } =
        mode === "sign-in"
          ? await client.auth.signInWithPassword({
              email,
              password,
              options: { captchaToken: token },
            })
          : await client.auth.signUp({
              email,
              password,
              options: { captchaToken: token },
            });
      if (authError) {
        resetCaptcha();
        setError(
          authError.message.toLowerCase().includes("captcha")
            ? "CAPTCHA verification failed. Try again."
            : authError.message,
        );
        return;
      }
      if (mode === "sign-up") {
        resetCaptcha();
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

  function switchMode(nextMode: Mode) {
    resetCaptcha();
    setCaptchaError(null);
    setMode(nextMode);
    setError(null);
    setNotice(null);
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
            onClick={() => switchMode(option)}
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

      <div className="mt-5">
        {HCAPTCHA_SITE_KEY ? (
          <HCaptcha
            ref={captchaRef}
            sitekey={HCAPTCHA_SITE_KEY}
            reCaptchaCompat={false}
            onVerify={(captchaResponse) => {
              setCaptchaToken(captchaResponse);
              setCaptchaError(null);
            }}
            onExpire={() => {
              setCaptchaToken(null);
              setCaptchaError("CAPTCHA expired. Please verify again.");
            }}
            onError={() => {
              setCaptchaToken(null);
              setCaptchaError("CAPTCHA could not be completed. Try again.");
            }}
          />
        ) : (
          <p
            role="alert"
            className="border-l-2 border-danger bg-surface-muted px-3 py-2 text-sm text-ink-soft"
          >
            hCaptcha is not configured. Set{" "}
            <code>NEXT_PUBLIC_HCAPTCHA_SITE_KEY</code> and rebuild the
            frontend.
          </p>
        )}
        {captchaError !== null && (
          <p role="alert" className="mt-2 text-xs text-danger">
            {captchaError}
          </p>
        )}
        {HCAPTCHA_SITE_KEY && captchaToken === null && captchaError === null ? (
          <p className="mt-2 text-xs text-muted">
            Complete the CAPTCHA to continue.
          </p>
        ) : null}
        <p className="mt-2 text-xs text-muted">
          This site is protected by hCaptcha. See our{" "}
          <Link
            href="/privacy"
            className="font-medium text-accent underline underline-offset-2"
          >
            Privacy Notice
          </Link>
          .
        </p>
      </div>

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
        disabled={
          submitting || !HCAPTCHA_SITE_KEY || captchaToken === null
        }
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
