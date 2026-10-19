"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "./auth/auth-provider";
import { CloseIcon, HubMarkIcon, MenuIcon } from "./icons";

const NAV_LINKS = [
  {
    href: "/",
    label: "Overview",
    match: (pathname: string) => pathname === "/",
  },
  {
    href: "/apps/resume-ats",
    label: "Resume ATS",
    match: (pathname: string) => pathname.startsWith("/apps/resume-ats"),
  },
  {
    href: "/apps/support",
    label: "IT Support",
    match: (pathname: string) => pathname.startsWith("/apps/support"),
  },
];

function accountInitial(email: string | undefined): string {
  const value = (email ?? "").trim();
  return value ? value[0].toUpperCase() : "A";
}

export function SiteHeader() {
  const pathname = usePathname();
  const { session, loading, configured, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  const email = session?.user.email ?? "";
  const nav = (
    <ul className="flex flex-col gap-1 md:flex-row md:items-center md:gap-1">
      {NAV_LINKS.map((link) => {
        const active = link.match(pathname);
        return (
          <li key={link.label}>
            <Link
              href={link.href}
              onClick={() => setMenuOpen(false)}
              aria-current={active ? "page" : undefined}
              className={`relative flex items-center rounded-lg px-3 py-2 text-sm transition-colors md:py-1.5 ${
                active
                  ? "bg-surface-muted font-semibold text-ink md:bg-transparent md:after:absolute md:after:inset-x-3 md:after:-bottom-[18px] md:after:h-0.5 md:after:rounded-full md:after:bg-accent"
                  : "font-medium text-muted hover:bg-surface-muted hover:text-ink"
              } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent`}
            >
              {link.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-canvas/85 backdrop-blur-xl">
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8"
      >
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-ink text-canvas">
            <HubMarkIcon className="h-4 w-4" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-ink">
            AI Hub
          </span>
        </Link>

        <div className="hidden md:block">{nav}</div>

        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          {loading ? (
            <span className="h-8 w-24 animate-pulse rounded-full bg-surface-muted" />
          ) : session !== null ? (
            <div className="hidden min-w-0 items-center gap-3 sm:flex">
              <span className="max-w-48 truncate text-sm text-muted lg:inline">
                {email}
              </span>
              <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-muted text-xs font-semibold text-ink"
              >
                {accountInitial(email)}
              </span>
              <Link
                href="/profile"
                className="rounded-lg px-2 py-1.5 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                Profile
              </Link>
              <button
                type="button"
                onClick={() => signOut()}
                className="rounded-lg px-2 py-1.5 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                Sign out
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className={
                configured
                  ? "ui-button ui-button-primary hidden sm:inline-flex"
                  : "hidden text-sm text-muted sm:inline"
              }
            >
              Sign in
            </Link>
          )}

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-ink transition-colors hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent md:hidden"
          >
            {menuOpen ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </nav>

      {menuOpen && (
        <div
          id="mobile-navigation"
          className="border-t border-line bg-surface px-4 py-4 shadow-sm md:hidden"
        >
          {nav}
          <div className="mt-4 border-t border-line pt-4">
            {session !== null ? (
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">
                    {email}
                  </p>
                  <p className="text-xs text-muted">Signed in</p>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href="/profile"
                    onClick={() => setMenuOpen(false)}
                    className="ui-button ui-button-secondary"
                  >
                    Profile
                  </Link>
                  <button
                    type="button"
                    onClick={() => signOut()}
                    className="ui-button ui-button-secondary"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            ) : (
              <Link
                href="/login"
                className={
                  configured
                    ? "ui-button ui-button-primary w-full"
                    : "text-sm text-muted"
                }
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
