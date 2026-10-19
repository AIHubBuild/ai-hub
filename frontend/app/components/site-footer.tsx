"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HubMarkIcon } from "./icons";

export function SiteFooter() {
  const pathname = usePathname();
  if (
    pathname === "/login" ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/auth")
  ) {
    return null;
  }

  return (
    <footer className="mt-auto border-t border-line">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink text-canvas">
            <HubMarkIcon className="h-3.5 w-3.5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">AI Hub</p>
            <p className="text-xs text-muted">
              Focused tools for work that needs a second pair of eyes.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
          <Link href="/" className="transition-colors hover:text-ink">
            Overview
          </Link>
          <Link
            href="/apps/resume-ats"
            className="transition-colors hover:text-ink"
          >
            Resume ATS
          </Link>
          <Link
            href="/apps/support"
            className="transition-colors hover:text-ink"
          >
            IT Support
          </Link>
          <Link href="/terms" className="transition-colors hover:text-ink">
            Terms
          </Link>
          <Link href="/privacy" className="transition-colors hover:text-ink">
            Privacy
          </Link>
          <span className="hidden h-3 w-px bg-line sm:inline" />
          <span>Private to your account</span>
        </div>
      </div>
    </footer>
  );
}
