"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAdminUsage,
  type AdminWindow,
  type AssistantId,
  type UsageData,
} from "../lib/admin";
import {
  AdminErrorState,
  AdminPageHeader,
  EmptyState,
  formatLatency,
  formatPercent,
  LoadingPanel,
  MetricCard,
  Panel,
  WindowPicker,
} from "./components/admin-ui";

export function UsageOverview() {
  const [range, setRange] = useState<AdminWindow>("7d");
  const [assistant, setAssistant] = useState<AssistantId | "">("");
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await fetchAdminUsage({ window: range, assistant });
        if (cancelled) {
          return;
        }
        setUsage(data);
        setError(null);
      } catch {
        if (!cancelled) {
          setError("The usage read model could not be loaded.");
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
  }, [range, assistant, refresh]);

  return (
    <div>
      <AdminPageHeader
        eyebrow="Usage overview"
        title="AI activity at a glance"
        description="Server-side aggregates from the existing AI run records. Token usage and cost remain unavailable until provider usage instrumentation is added."
      />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <WindowPicker
          value={range}
          onChange={(value) => {
            setLoading(true);
            setRange(value);
          }}
        />
        <label className="flex items-center gap-2 text-xs font-medium text-muted">
          Assistant
          <select
            value={assistant}
            onChange={(event) => {
              setLoading(true);
              setAssistant(event.target.value as AssistantId | "");
            }}
            className="ui-field w-auto py-2"
          >
            <option value="">All assistants</option>
            <option value="resume_ats">Resume ATS</option>
            <option value="support_copilot">IT Support Copilot</option>
          </select>
        </label>
      </div>

      {loading ? (
        <div className="mt-6">
          <LoadingPanel label="Loading usage summary…" />
        </div>
      ) : error ? (
        <div className="mt-6">
          <AdminErrorState
            title="Usage unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        </div>
      ) : usage ? (
        <div className="mt-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total requests"
              value={new Intl.NumberFormat().format(usage.total_requests)}
            />
            <MetricCard
              label="Success rate"
              value={formatPercent(usage.success_rate)}
              detail={`${usage.successful_requests} successful`}
            />
            <MetricCard
              label="Failed requests"
              value={new Intl.NumberFormat().format(usage.failed_requests)}
              detail={formatPercent(usage.failure_rate)}
            />
            <MetricCard
              label="Average latency"
              value={formatLatency(usage.average_latency_ms)}
              detail={`Max ${formatLatency(usage.max_latency_ms)}`}
            />
          </div>

          <Panel
            title="By assistant"
            description="Request counts and latency for the selected window."
          >
            {usage.by_assistant.length === 0 ? (
              <EmptyState
                title="No usage in this window"
                message="No AI requests were recorded for the selected period and assistant."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Assistant</th>
                      <th className="pb-3 pr-4 font-medium">Requests</th>
                      <th className="pb-3 pr-4 font-medium">Successful</th>
                      <th className="pb-3 pr-4 font-medium">Failed</th>
                      <th className="pb-3 font-medium">Average latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.by_assistant.map((row) => (
                      <tr key={row.assistant} className="border-b border-line/60 last:border-0">
                        <td className="py-3 pr-4 font-medium text-ink">
                          {row.assistant === "resume_ats"
                            ? "Resume ATS"
                            : row.assistant === "support_copilot"
                              ? "IT Support Copilot"
                              : row.assistant}
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {row.total_requests}
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {row.successful_requests}
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {row.failed_requests}
                        </td>
                        <td className="py-3 text-muted">
                          {formatLatency(row.average_latency_ms)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid gap-4 sm:grid-cols-2">
            <Link
              href="/admin/requests"
              className="rounded-2xl bg-surface p-5 ring-1 ring-line/80 transition-colors hover:bg-surface-muted"
            >
              <p className="text-sm font-semibold text-ink">
                Investigate AI requests
              </p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Search failures and open sanitized request details.
              </p>
            </Link>
            <Link
              href="/admin/audit"
              className="rounded-2xl bg-surface p-5 ring-1 ring-line/80 transition-colors hover:bg-surface-muted"
            >
              <p className="text-sm font-semibold text-ink">
                Review audit events
              </p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Inspect administrator actions and denied access attempts.
              </p>
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
