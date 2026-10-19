"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getSupabase } from "../../lib/supabase";

type VerificationType =
  | "signup"
  | "invite"
  | "magiclink"
  | "recovery"
  | "email_change"
  | "email";

type Status = "loading" | "error" | "pending";

const VALID_TYPES = new Set<VerificationType>([
  "signup",
  "invite",
  "magiclink",
  "recovery",
  "email_change",
  "email",
]);

function safeMessage(raw: string): string {
  const message = raw.toLowerCase();
  if (message.includes("code verifier") || message.includes("pkce")) {
    return "This confirmation link was opened in a different browser or device. Sign in here and request a new confirmation email if needed.";
  }
  if (
    message.includes("expired") ||
    message.includes("invalid") ||
    message.includes("token")
  ) {
    return "This confirmation link is invalid or has expired. Sign in and request a new confirmation email.";
  }
  return "The confirmation link could not be completed. Sign in and request a new confirmation email.";
}

export function AuthCallbackView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const started = useRef(false);
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("Verifying your email address…");

  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const rawType = searchParams.get("type") ?? "email";
  const errorParam = searchParams.get("error");
  const errorDescription = searchParams.get("error_description") ?? "";
  const otpType: VerificationType = VALID_TYPES.has(
    rawType as VerificationType,
  )
    ? (rawType as VerificationType)
    : "email";

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    let active = true;

    const finish = (nextStatus: Status, nextMessage: string) => {
      if (active) {
        setStatus(nextStatus);
        setMessage(nextMessage);
      }
    };

    const run = async () => {
      await Promise.resolve();
      if (!active) {
        return;
      }

      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", "/auth/callback");
      }

      if (errorParam) {
        finish(
          "error",
          errorDescription.toLowerCase().includes("expired")
            ? "This confirmation link has expired. Sign in and request a new confirmation email."
            : "This confirmation link is invalid or has already been used. Sign in and request a new confirmation email.",
        );
        return;
      }

      const client = getSupabase();
      if (client === null) {
        finish("error", "Authentication is not configured for this deployment.");
        return;
      }

      try {
        if (tokenHash) {
          const { error } = await client.auth.verifyOtp({
            token_hash: tokenHash,
            type: otpType,
          });
          if (error) {
            finish("error", safeMessage(error.message));
            return;
          }
        } else if (code) {
          const { error } = await client.auth.exchangeCodeForSession(code);
          if (error) {
            finish("error", safeMessage(error.message));
            return;
          }
        }

        const { data } = await client.auth.getSession();
        if (data.session === null) {
          finish(
            "error",
            "No verified session was created. Sign in and request a new confirmation email.",
          );
          return;
        }

        if (!data.session.user.email_confirmed_at) {
          finish(
            "pending",
            "Your email is not confirmed yet. Check your inbox or request a new confirmation email after signing in.",
          );
          return;
        }

        router.replace("/register/complete");
        router.refresh();
      } catch (caught) {
        const raw = caught instanceof Error ? caught.message : "";
        finish("error", safeMessage(raw));
      }
    };

    void run();

    return () => {
      active = false;
    };
  }, [
    code,
    errorDescription,
    errorParam,
    otpType,
    router,
    tokenHash,
  ]);

  return (
    <section className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
      <p className="ui-eyebrow">Email verification</p>
      <h1 className="ui-display mt-3 text-3xl text-ink">
        {status === "loading"
          ? "Verifying your email"
          : status === "pending"
            ? "Verification pending"
            : "Confirmation link problem"}
      </h1>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted">
        {message}
      </p>

      {status !== "loading" && (
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <Link href="/login" className="ui-button ui-button-primary">
            Sign in and resend
          </Link>
          <Link href="/" className="ui-button ui-button-secondary">
            Back to AI Hub
          </Link>
        </div>
      )}
    </section>
  );
}
