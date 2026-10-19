"use client";

import HCaptcha from "@hcaptcha/react-hcaptcha";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { fetchProfile, PROFILE_POLICY_VERSION } from "../lib/profile";
import { getSupabase } from "../lib/supabase";
import { PasswordInput } from "../components/auth/password-input";
import { Spinner } from "../components/auth/spinner";

type Mode = "sign-in" | "sign-up" | "verify-email";

type FieldErrors = {
  fullName?: string;
  email?: string;
  password?: string;
  policies?: string;
};

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
  const redirect =
    rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
      ? rawRedirect
      : "/";

  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [acceptedPolicies, setAcceptedPolicies] = useState(false);
  const [pendingEmail, setPendingEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState<string | null>(null);
  const captchaRef = useRef<HCaptcha>(null);

  const supabase = getSupabase();

  if (supabase === null) {
    return (
      <div className="auth-message-error rounded-2xl border p-5 text-center text-sm">
        Supabase authentication is not configured for this deployment.
      </div>
    );
  }

  function resetCaptcha() {
    captchaRef.current?.resetCaptcha();
    setCaptchaToken(null);
  }

  function validateCaptcha(): string | null {
    if (!HCAPTCHA_SITE_KEY) {
      return "hCaptcha is not configured. Add NEXT_PUBLIC_HCAPTCHA_SITE_KEY and rebuild the frontend.";
    }
    if (captchaToken === null) {
      return "Complete the CAPTCHA to continue.";
    }
    return null;
  }

  function switchMode(nextMode: Mode) {
    resetCaptcha();
    setCaptchaError(null);
    setFieldErrors({});
    setMode(nextMode);
    setError(null);
    setNotice(null);
  }

  function validateSignUpFields(): FieldErrors {
    const errors: FieldErrors = {};
    if (fullName.trim().length < 2) {
      errors.fullName = "Enter your full name.";
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (password.length < 8) {
      errors.password = "Use at least 8 characters.";
    }
    if (!acceptedPolicies) {
      errors.policies = "Accept the Terms of Service and Privacy Notice.";
    }
    return errors;
  }

  function validateSignInFields(): FieldErrors {
    const errors: FieldErrors = {};
    if (!EMAIL_PATTERN.test(email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (!password) {
      errors.password = "Enter your password.";
    }
    return errors;
  }

  async function handleSignUp() {
    const client = getSupabase();
    if (client === null) {
      return;
    }
    const errors = validateSignUpFields();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }
    if (captchaToken === null) {
      setError("Complete the CAPTCHA to continue.");
      return;
    }

    const { data, error: authError } = await client.auth.signUp({
      email: email.trim(),
      password,
      options: {
        emailRedirectTo: verificationCallbackUrl(),
        captchaToken,
        data: {
          full_name: fullName.trim(),
          terms_accepted: true,
          privacy_accepted: true,
          terms_version: PROFILE_POLICY_VERSION,
          privacy_version: PROFILE_POLICY_VERSION,
        },
      },
    });

    if (authError) {
      resetCaptcha();
      const message = authError.message.toLowerCase();
      if (message.includes("already registered")) {
        setError(
          "An account may already exist for this email. Sign in or reset your password.",
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
    const errors = validateSignInFields();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }
    if (captchaToken === null) {
      setError("Complete the CAPTCHA to continue.");
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
      // Protected pages enforce account and profile access server-side.
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
      setError("Complete the CAPTCHA to resend.");
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
    setFieldErrors({});

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

  const heading =
    mode === "sign-in"
      ? "Welcome back"
      : mode === "sign-up"
        ? "Create your account"
        : "Check your inbox";

  const supportingText =
    mode === "sign-in"
      ? "Sign in to continue to your private AI workspace."
      : mode === "sign-up"
        ? "Create your account, verify your email, then add your location and optional profile details."
        : "Confirm your email address before completing registration.";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {mode !== "verify-email" && (
        <div className="text-center">
          <p className="ui-eyebrow">AI Hub Assist</p>
          <h1 className="mt-3 text-[28px] font-semibold tracking-[-0.035em] text-ink sm:text-[32px]">
            {heading}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted">
            {supportingText}
          </p>
        </div>
      )}

      {mode !== "verify-email" && (
        <div
          role="tablist"
          aria-label="Authentication mode"
          className="grid grid-cols-2 gap-1 rounded-xl border border-line bg-surface-muted p-1"
        >
          {(["sign-in", "sign-up"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={mode === option}
              onClick={() => switchMode(option)}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                mode === option
                  ? "bg-surface text-ink shadow-sm ring-1 ring-white/10"
                  : "text-muted hover:text-ink"
              }`}
            >
              {option === "sign-in" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>
      )}

      {mode === "verify-email" ? (
        <div className="text-center">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/25 bg-accent-soft text-2xl text-accent">
            ✉
          </span>
          <h1 className="mt-5 text-[26px] font-semibold tracking-[-0.03em] text-ink">
            {heading}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            We sent a confirmation link to{" "}
            <span className="font-medium text-ink">
              {pendingEmail || "your email address"}
            </span>
            .
          </p>
          <p className="mt-3 text-xs leading-5 text-muted">
            Open the link in this browser to continue. If you opened it on
            another device, sign in here or request a new email below.
          </p>
        </div>
      ) : (
        <>
          {mode === "sign-up" && (
            <div>
              <label
                htmlFor="full-name"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
              >
                Full name
              </label>
              <input
                id="full-name"
                type="text"
                required
                minLength={2}
                maxLength={200}
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                aria-invalid={fieldErrors.fullName ? true : undefined}
                aria-describedby={
                  fieldErrors.fullName ? "full-name-error" : undefined
                }
                className="ui-field"
              />
              {fieldErrors.fullName && (
                <p id="full-name-error" className="auth-field-error mt-1.5 text-xs">
                  {fieldErrors.fullName}
                </p>
              )}
            </div>
          )}

          <div>
            <label
              htmlFor="email"
              className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
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
              aria-invalid={fieldErrors.email ? true : undefined}
              aria-describedby={
                fieldErrors.email ? "email-error" : undefined
              }
              className="ui-field"
            />
            {fieldErrors.email && (
              <p id="email-error" className="auth-field-error mt-1.5 text-xs">
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
            >
              Password
            </label>
            <PasswordInput
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete={
                mode === "sign-in" ? "current-password" : "new-password"
              }
              minLength={mode === "sign-up" ? 8 : undefined}
              invalid={Boolean(fieldErrors.password)}
              describedBy={
                fieldErrors.password ? "password-error" : undefined
              }
            />
            {mode === "sign-up" && !fieldErrors.password && (
              <p className="mt-1.5 text-[11px] text-muted">
                At least 8 characters.
              </p>
            )}
            {fieldErrors.password && (
              <p id="password-error" className="auth-field-error mt-1.5 text-xs">
                {fieldErrors.password}
              </p>
            )}
          </div>

          {mode === "sign-up" && (
            <div>
              <label className="flex items-start gap-2.5 text-xs leading-5 text-ink-soft">
                <input
                  type="checkbox"
                  required
                  checked={acceptedPolicies}
                  onChange={(event) => setAcceptedPolicies(event.target.checked)}
                  aria-invalid={fieldErrors.policies ? true : undefined}
                  aria-describedby={
                    fieldErrors.policies ? "policies-error" : undefined
                  }
                  className="mt-0.5 h-4 w-4 rounded border-line"
                />
                <span>
                  I accept the{" "}
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
                </span>
              </label>
              {fieldErrors.policies && (
                <p
                  id="policies-error"
                  className="auth-field-error mt-1.5 text-xs"
                >
                  {fieldErrors.policies}
                </p>
              )}
            </div>
          )}
        </>
      )}

      <div className="pt-1">
        {HCAPTCHA_SITE_KEY ? (
          <HCaptcha
            ref={captchaRef}
            sitekey={HCAPTCHA_SITE_KEY}
            theme="dark"
            reCaptchaCompat={false}
            onVerify={(token) => {
              setCaptchaToken(token);
              setCaptchaError(null);
            }}
            onExpire={() => {
              setCaptchaToken(null);
              setCaptchaError("CAPTCHA expired. Verify again to continue.");
            }}
            onError={() => {
              setCaptchaToken(null);
              setCaptchaError("CAPTCHA could not be completed. Try again.");
            }}
          />
        ) : (
          <p
            role="alert"
            className="auth-message-error rounded-xl border px-3 py-2 text-xs"
          >
            hCaptcha is not configured. Add NEXT_PUBLIC_HCAPTCHA_SITE_KEY and
            rebuild the frontend.
          </p>
        )}
        {captchaError && (
          <p role="alert" className="auth-field-error mt-2 text-xs">
            {captchaError}
          </p>
        )}
        {HCAPTCHA_SITE_KEY && captchaToken === null && !captchaError && (
          <p className="mt-2 text-[11px] text-muted">
            {mode === "verify-email"
              ? "Complete the CAPTCHA to resend the confirmation email."
              : "Complete the CAPTCHA to continue."}
          </p>
        )}
        <p className="mt-2 text-[11px] leading-5 text-muted">
          Protected by hCaptcha. See our{" "}
          <Link
            href="/privacy"
            className="font-medium text-accent underline underline-offset-2"
          >
            Privacy Notice
          </Link>
          .
        </p>
      </div>

      {error && (
        <p role="alert" className="auth-message-error rounded-xl border px-3 py-2 text-sm">
          {error}
        </p>
      )}
      {notice && (
        <p className="auth-message-success rounded-xl border px-3 py-2 text-sm">
          {notice}
        </p>
      )}

      {mode === "verify-email" ? (
        <div className="space-y-2">
          <button
            type="button"
            onClick={handleResend}
            disabled={resending || !HCAPTCHA_SITE_KEY || captchaToken === null}
            className="ui-button ui-button-primary h-11 w-full"
          >
            {resending && <Spinner />}
            {resending ? "Sending…" : "Resend confirmation email"}
          </button>
          <button
            type="button"
            onClick={() => switchMode("sign-in")}
            className="ui-button ui-button-secondary h-11 w-full"
          >
            Back to sign in
          </button>
        </div>
      ) : (
        <button
          type="submit"
          disabled={submitting || !HCAPTCHA_SITE_KEY || captchaToken === null}
          className="ui-button ui-button-primary h-11 w-full"
        >
          {submitting && <Spinner />}
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
