"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAdminRequests,
  type AdminWindow,
  type AssistantId,
  type RequestListData,
  type RequestStatus,
} from "../../lib/admin";
import {
  AdminErrorState,
  AdminPageHeader,
  EmptyState,
  formatDateTime,
  formatLatency,
  LoadingPanel,
  Pagination,
  Panel,
  StatusPill,
  WindowPicker,
} from "../components/admin-ui";

export function RequestsView() {
  const [range, setRange] = useState<AdminWindow>("30d");
  const [status, setStatus] = useState<RequestStatus | "">("");
  const [assistant, setAssistant] = useState<AssistantId | "">("");
  const [userId, setUserId] = useState("");
  const [errorCategory, setErrorCategory] = useState("");
  const [draftUserId, setDraftUserId] = useState("");
  const [draftCategory, setDraftCategory] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<RequestListData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminRequests({
          window: range,
          status,
          assistant,
          userId,
          errorCategory,
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
          setError("The AI request read model could not be loaded.");
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
  }, [range, status, assistant, userId, errorCategory, page, refresh]);

  function applyFilters() {
    setLoading(true);
    setUserId(draftUserId.trim());
    setErrorCategory(draftCategory.trim());
    setPage(1);
  }

  return (
    <div>
      <AdminPageHeader
        eyebrow="AI requests"
        title="Request investigation"
        description="Search sanitized AI run records. Inputs, outputs, prompts, resumes, support conversations, and raw exception messages are never returned."
      />

      <div className="mt-6 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <WindowPicker
            value={range}
            onChange={(value) => {
              setLoading(true);
              setRange(value);
              setPage(1);
            }}
          />
          <label className="flex items-center gap-2 text-xs font-medium text-muted">
            Assistant
            <select
              value={assistant}
              onChange={(event) => {
                setLoading(true);
                setAssistant(event.target.value as AssistantId | "");
                setPage(1);
              }}
              className="ui-field w-auto py-2"
            >
              <option value="">All assistants</option>
              <option value="resume_ats">Resume ATS</option>
              <option value="support_copilot">IT Support Copilot</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs font-medium text-muted">
            Status
            <select
              value={status}
              onChange={(event) => {
                setLoading(true);
                setStatus(event.target.value as RequestStatus | "");
                setPage(1);
              }}
              className="ui-field w-auto py-2"
            >
              <option value="">All statuses</option>
              <option value="success">Success</option>
              <option value="error">Failed</option>
            </select>
          </label>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters();
          }}
          className="grid gap-3 rounded-2xl bg-surface p-4 ring-1 ring-line/80 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <label className="text-xs font-medium text-muted">
            User ID
            <input
              value={draftUserId}
              onChange={(event) => setDraftUserId(event.target.value)}
              placeholder="Supabase user UUID"
              className="ui-field mt-1.5"
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Error category
            <input
              value={draftCategory}
              onChange={(event) => setDraftCategory(event.target.value)}
              placeholder="For example ProviderError"
              className="ui-field mt-1.5"
            />
          </label>
          <button type="submit" className="ui-button ui-button-secondary self-end">
            Apply filters
          </button>
        </form>
        <p className="text-xs leading-5 text-muted">
          Historical records without a stored error category may not match the
          category filter. Their detail view still shows a safe derived type.
        </p>
      </div>

      <div className="mt-6">
        {loading ? (
          <LoadingPanel label="Loading AI requests…" />
        ) : error ? (
          <AdminErrorState
            title="Requests unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        ) : data ? (
          <Panel
            title="Request records"
            description={`${data.total.toLocaleString()} records in the selected window.`}
          >
            {data.items.length === 0 ? (
              <EmptyState
                title="No requests found"
                message="No AI requests match the selected filters."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[920px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Time</th>
                      <th className="pb-3 pr-4 font-medium">Assistant</th>
                      <th className="pb-3 pr-4 font-medium">Status</th>
                      <th className="pb-3 pr-4 font-medium">Request</th>
                      <th className="pb-3 pr-4 font-medium">User</th>
                      <th className="pb-3 pr-4 font-medium">Latency</th>
                      <th className="pb-3 font-medium">Error</th>
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
                        <td className="py-3 pr-4">
                          <Link
                            href={`/admin/users/${item.user_id}`}
                            className="font-mono text-xs text-muted underline-offset-4 hover:text-ink hover:underline"
                          >
                            {item.user_id.slice(0, 13)}…
                          </Link>
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {formatLatency(item.latency_ms)}
                        </td>
                        <td className="py-3 text-muted">
                          {item.error_category ?? "None"}
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
