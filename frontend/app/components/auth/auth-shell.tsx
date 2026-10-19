import Link from "next/link";
import { HubMarkIcon } from "../icons";

export function AuthShell({
  children,
  width = "default",
}: {
  children: React.ReactNode;
  width?: "default" | "wide";
}) {
  return (
    <main className="auth-shell relative flex min-h-screen flex-col overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(109,131,255,0.16),transparent_38%),radial-gradient(circle_at_85%_15%,rgba(139,92,246,0.11),transparent_34%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent"
      />

      <div className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8 sm:py-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-canvas shadow-lg shadow-black/20">
            <HubMarkIcon className="h-4 w-4" />
          </span>
          <span className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-ink">
              AI Hub Assist
            </span>
            <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
              Private workspace
            </span>
          </span>
        </Link>
        <Link
          href="/"
          className="text-xs font-medium text-muted transition-colors hover:text-ink"
        >
          Back to home
        </Link>
      </div>

      <div className="relative z-10 flex flex-1 items-start justify-center px-4 pb-8 pt-2 sm:items-center sm:px-6 sm:pb-12">
        <div
          className={`w-full ${width === "wide" ? "max-w-2xl" : "max-w-[440px]"}`}
        >
          <div className="auth-card rounded-3xl p-6 sm:p-8">{children}</div>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[11px] text-muted">
            <Link
              href="/terms"
              className="transition-colors hover:text-ink"
            >
              Terms of Service
            </Link>
            <span aria-hidden="true" className="h-3 w-px bg-line" />
            <Link
              href="/privacy"
              className="transition-colors hover:text-ink"
            >
              Privacy Notice
            </Link>
            <span aria-hidden="true" className="h-3 w-px bg-line" />
            <span>Protected by hCaptcha</span>
          </div>
        </div>
      </div>
    </main>
  );
}
