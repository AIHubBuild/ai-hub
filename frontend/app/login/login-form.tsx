"use client";

import HCaptcha from "@hcaptcha/react-hcaptcha";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { fetchProfile } from "../lib/profile";
import { getSupabase } from "../lib/supabase";

type Mode = "sign-in" | "sign-up" | "verify-email";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const HCAPTCHA_SITE_KEY = (
  process.env.NEXT_PUBLIC_HCAPTCHA_SITE_KEY ?? ""
).trim();

function verificationCallbackUrl(): string {
  return `${window.location.origin}/auth/callback`;
}

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
  const [pendingEmail, setPendingEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
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

  function switchMode(nextMode: Mode) {
    resetCaptcha();
    setCaptchaError(null);
    setMode(nextMode);
    setError(null);
    setNotice(null);
  }

  async function handleSignUp() {
    const client = getSupabase();
    if (client === null) {
      return;
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (captchaToken === null) {
      setError("Complete the CAPTCHA before continuing.");
      return;
    }

    const { data, error: authError } = await client.auth.signUp({
      email: email.trim(),
      password,
      options: {
        emailRedirectTo: verificationCallbackUrl(),
        captchaToken,
      },
    });

    if (authError) {
      resetCaptcha();
      const message = authError.message.toLowerCase();
      if (message.includes("already registered")) {
        setError(
          "An account may already exist for this email. Sign in or reset the password.",
        );
      } else if (message.includes("captcha")) {
        setError("CAPTCHA verification failed. Try again.");
      } else {
        setError(authError.message);
      }
      return;
    }

    resetCaptcha();

    if (data.session !== null) {
      if (data.session.user.email_confirmed_at) {
        router.push("/register/complete");
        router.refresh();
        return;
      }
      await client.auth.signOut();
    }

    setPendingEmail(email.trim());
    setMode("verify-email");
    setNotice(
      "We sent a confirmation email. Confirm your address before completing your profile.",
    );
  }

  async function handleSignIn() {
    const client = getSupabase();
    if (client === null) {
      return;
    }
    if (!EMAIL_PATTERN.test(email.trim()) || !password) {
      setError("Enter your email address and password.");
      return;
    }
    if (captchaToken === null) {
      setError("Complete the CAPTCHA before continuing.");
      return;
    }

    const { data, error: authError } =
      await client.auth.signInWithPassword({
        email: email.trim(),
        password,
        options: { captchaToken },
      });

    if (authError) {
      resetCaptcha();
      const message = authError.message.toLowerCase();
      if (message.includes("email not confirmed")) {
        setPendingEmail(email.trim());
        setMode("verify-email");
        setError(null);
        setNotice(
          "Your email is not confirmed yet. Check your inbox or resend the confirmation email.",
        );
      } else if (message.includes("captcha")) {
        setError("CAPTCHA verification failed. Try again.");
      } else {
        setError(authError.message);
      }
      return;
    }

    resetCaptcha();

    if (!data.session?.user.email_confirmed_at) {
      await client.auth.signOut();
      setPendingEmail(email.trim());
      setMode("verify-email");
      setNotice(
        "Your email is not confirmed yet. Check your inbox or resend the confirmation email.",
      );
      return;
    }

    try {
      const profile = await fetchProfile();
      if (profile === null) {
        router.push("/register/complete");
        router.refresh();
        return;
      }
    } catch {
      // Keep the existing destination; protected pages will enforce access.
    }

    router.push(redirect);
    router.refresh();
  }

  async function handleResend() {
    const client = getSupabase();
    if (client === null || !pendingEmail) {
      return;
    }
    const captchaValidationError = validateCaptcha();
    if (captchaValidationError !== null) {
      setError(captchaValidationError);
      return;
    }
    if (captchaToken === null) {
      setError("Complete the CAPTCHA before resending.");
      return;
    }

    setResending(true);
    setError(null);
    setNotice(null);
    try {
      const { error: resendError } = await client.auth.resend({
        type: "signup",
        email: pendingEmail,
        options: {
          emailRedirectTo: verificationCallbackUrl(),
          captchaToken,
        },
      });
      resetCaptcha();
      if (resendError) {
        const status = (resendError as { status?: number }).status;
        if (
          status === 429 ||
          resendError.message.toLowerCase().includes("rate")
        ) {
          setError(
            "Too many confirmation requests. Please wait before trying again.",
          );
        } else if (resendError.message.toLowerCase().includes("captcha")) {
          setError("CAPTCHA verification failed. Try again.");
        } else {
          setError(resendError.message);
        }
        return;
      }
      setNotice("Confirmation email sent again. Check your inbox.");
    } finally {
      setResending(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    const captchaValidationError = validateCaptcha();
    if (captchaValidationError !== null) {
      setError(captchaValidationError);
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "sign-in") {
        await handleSignIn();
      } else if (mode === "sign-up") {
        await handleSignUp();
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl bg-surface p-6 ring-1 ring-line/80 sm:p-7"
    >
      {mode !== "verify-email" && (
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
      )}

      {mode === "verify-email" ? (
        <div>
          <p className="ui-eyebrow">Verify your email</p>
          <h2 className="ui-display mt-2 text-2xl text-ink">
            Check your inbox
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            We sent a confirmation link to{" "}
            <span className="font-medium text-ink">
              {pendingEmail || "your email address"}
            </span>
            . Open the link in this browser to verify your email and continue
            registration.
          </p>
          <p className="mt-3 text-xs leading-5 text-muted">
            If you opened the link on another device, sign in again here or
            request a new confirmation email below.
          </p>
          <button
            type="button"
            onClick={handleResend}
            disabled={
              resending || !HCAPTCHA_SITE_KEY || captchaToken === null
            }
            className="ui-button ui-button-primary mt-5 w-full"
          >
            {resending ? "Sending…" : "Resend confirmation email"}
          </button>
          <button
            type="button"
            onClick={() => switchMode("sign-in")}
            className="ui-button ui-button-secondary mt-2 w-full"
          >
            Back to sign in
          </button>
        </div>
      ) : (
        <>
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
            autoComplete={
              mode === "sign-in" ? "current-password" : "new-password"
            }
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="ui-field"
          />
          {mode === "sign-up" && (
            <p className="mt-2 text-xs leading-5 text-muted">
              After confirming your email, you will provide your profile
              details. By creating an account you agree to the{" "}
              <Link
                href="/terms"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-accent underline underline-offset-2"
              >
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link
                href="/privacy"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-accent underline underline-offset-2"
              >
                Privacy Notice
              </Link>
              .
            </p>
          )}
        </>
      )}

      <div className="mt-5">
        {HCAPTCHA_SITE_KEY ? (
          <HCaptcha
            ref={captchaRef}
            sitekey={HCAPTCHA_SITE_KEY}
            reCaptchaCompat={false}
            onVerify={(token) => {
              setCaptchaToken(token);
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
            {mode === "verify-email"
              ? "Complete the CAPTCHA to resend the confirmation email."
              : "Complete the CAPTCHA to continue."}
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

      {mode !== "verify-email" && (
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
      )}
    </form>
  );
}
