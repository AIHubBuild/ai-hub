"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { fetchAdminMe, type AdminMeData } from "../../lib/admin";
import { useAuth } from "../../components/auth/auth-provider";
import { AdminErrorState, LoadingPanel } from "./admin-ui";

const NAV_ITEMS = [
  { href: "/admin", label: "Overview", exact: true },
  { href: "/admin/requests", label: "AI Requests", exact: false },
  { href: "/admin/audit", label: "Audit Log", exact: false },
  { href: "/admin/incidents", label: "Incidents", exact: false },
  { href: "/admin/subscriptions", label: "Subscriptions", exact: false },
  { href: "/admin/users", label: "Users", exact: false },
];

type AccessState = "loading" | "ready" | "unauthenticated" | "forbidden" | "error";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { session, loading: authLoading, configured } = useAuth();
  const [state, setState] = useState<AccessState>("loading");
  const [admin, setAdmin] = useState<AdminMeData | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!configured || session === null) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const data = await fetchAdminMe();
        if (cancelled) {
          return;
        }
        setAdmin(data);
        setState("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          setState("unauthenticated");
          return;
        }
        if (error instanceof ApiError && error.status === 403) {
          setState("forbidden");
          return;
        }
        setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [configured, session, refresh]);

  const effectiveState: AccessState = authLoading
    ? "loading"
    : !configured || session === null
      ? "unauthenticated"
      : state;

  const redirect = encodeURIComponent(pathname);

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
      <header className="border-b border-line pb-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="ui-eyebrow">Private administration</p>
            <h1 className="ui-display mt-3 text-3xl text-ink sm:text-4xl">
              Reliability console
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
              Read-only operational visibility for AI Hub. Every admin
              request is authorized by the backend.
            </p>
          </div>
          {effectiveState === "ready" && admin?.email ? (
            <p className="max-w-56 truncate text-xs text-muted">
              {admin.email}
            </p>
          ) : null}
        </div>
      </header>

      {effectiveState === "loading" ? (
        <div className="mt-8">
          <LoadingPanel label="Verifying administrator access…" />
        </div>
      ) : effectiveState === "unauthenticated" ? (
        <div className="mt-8">
          <div className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
            <p className="ui-eyebrow">Sign in required</p>
            <h2 className="ui-display mt-3 text-2xl text-ink">
              Administrator access requires authentication
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
              {configured
                ? "Sign in with an administrator account to continue."
                : "Supabase authentication is not configured for this deployment."}
            </p>
            {configured ? (
              <Link
                href={`/login?redirect=${redirect}`}
                className="ui-button ui-button-primary mt-5"
              >
                Sign in
              </Link>
            ) : null}
          </div>
        </div>
      ) : effectiveState === "forbidden" ? (
        <div className="mt-8">
          <AdminErrorState
            title="Administrator access required"
            message="Your account is authenticated but does not have administrator access."
          />
        </div>
      ) : effectiveState === "error" ? (
        <div className="mt-8">
          <AdminErrorState
            title="Could not verify administrator access"
            message="The admin authorization check failed. No administrative data was loaded."
            onRetry={() => {
              setState("loading");
              setRefresh((value) => value + 1);
            }}
          />
        </div>
      ) : (
        <>
          <nav aria-label="Admin sections" className="mt-6">
            <ul className="flex flex-wrap gap-1 border-b border-line pb-2">
              {NAV_ITEMS.map((item) => {
                const active = item.exact
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`inline-flex rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                        active
                          ? "bg-surface font-semibold text-ink shadow-sm"
                          : "font-medium text-muted hover:bg-surface-muted hover:text-ink"
                      }`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="mt-8">{children}</div>
        </>
      )}
    </main>
  );
}
