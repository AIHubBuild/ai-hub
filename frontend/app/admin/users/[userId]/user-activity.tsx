"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAdminRequests,
  type RequestListData,
} from "../../../lib/admin";
import {
  AdminErrorState,
  EmptyState,
  formatDateTime,
  formatLatency,
  LoadingPanel,
  Pagination,
  Panel,
  StatusPill,
} from "../../components/admin-ui";

export function UserActivity({ userId }: { userId: string }) {
  const [data, setData] = useState<RequestListData | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminRequests({
          window: "30d",
          userId,
          page,
          pageSize: 25,
        });
        if (cancelled) {
          return;
        }
        setData(next);
        setError(null);
      } catch {
        if (!cancelled) {
          setError(
            "User activity could not be loaded. Confirm the ID is a valid Supabase user UUID.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, page, refresh]);

  return (
    <div>
      <Link
        href="/admin/users"
        className="inline-flex text-sm font-medium text-muted underline-offset-4 hover:text-ink hover:underline"
      >
        ← Back to users
      </Link>

      <header className="mt-5 border-b border-line pb-6">
        <p className="ui-eyebrow">Read-only user activity</p>
        <h1 className="ui-display mt-3 break-all text-2xl text-ink sm:text-3xl">
          {userId}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
          AI requests recorded in the last 30 days for this user ID. Account
          email, status, subscription, and privileged actions are unavailable
          until Supabase Admin API access is verified.
        </p>
        <Link
          href={`/admin/incidents?linked_user_id=${encodeURIComponent(userId)}`}
          className="ui-button ui-button-secondary mt-4"
        >
          Create incident for user
        </Link>
      </header>

      <div className="mt-6">
        {loading ? (
          <LoadingPanel label="Loading user activity…" />
        ) : error ? (
          <AdminErrorState
            title="User activity unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        ) : data ? (
          <Panel
            title="AI request activity"
            description={`${data.total.toLocaleString()} requests in the last 30 days.`}
          >
            {data.items.length === 0 ? (
              <EmptyState
                title="No activity found"
                message="No AI requests were recorded for this user ID in the last 30 days."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Time</th>
                      <th className="pb-3 pr-4 font-medium">Assistant</th>
                      <th className="pb-3 pr-4 font-medium">Status</th>
                      <th className="pb-3 pr-4 font-medium">Request</th>
                      <th className="pb-3 font-medium">Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => (
                      <tr
                        key={item.run_id}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="py-3 pr-4 text-muted">
                          {formatDateTime(item.created_at)}
                        </td>
                        <td className="py-3 pr-4 text-ink">
                          {item.assistant === "resume_ats"
                            ? "Resume ATS"
                            : item.assistant === "support_copilot"
                              ? "IT Support Copilot"
                              : item.assistant}
                        </td>
                        <td className="py-3 pr-4">
                          <StatusPill status={item.status} />
                        </td>
                        <td className="py-3 pr-4">
                          <Link
                            href={`/admin/requests/${item.run_id}`}
                            className="font-mono text-xs text-accent underline-offset-4 hover:underline"
                          >
                            {item.run_id.slice(0, 13)}…
                          </Link>
                        </td>
                        <td className="py-3 text-muted">
                          {formatLatency(item.latency_ms)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              onPageChange={(next) => {
                setLoading(true);
                setPage(next);
              }}
            />
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
