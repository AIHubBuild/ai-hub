import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthShell } from "../components/auth/auth-shell";
import { Spinner } from "../components/auth/spinner";
import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in or create your AI Hub Assist account.",
};

export default function LoginPage() {
  return (
    <AuthShell>
      <Suspense
        fallback={
          <div className="flex items-center justify-center py-12 text-sm text-muted">
            <Spinner className="mr-2" />
            Loading secure sign-in…
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
