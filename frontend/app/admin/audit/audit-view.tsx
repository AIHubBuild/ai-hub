"use client";

import { useEffect, useState } from "react";
import {
  fetchAdminAudit,
  type AdminWindow,
  type AuditListData,
} from "../../lib/admin";
import {
  AdminErrorState,
  AdminPageHeader,
  EmptyState,
  formatDateTime,
  LoadingPanel,
  Pagination,
  Panel,
  WindowPicker,
} from "../components/admin-ui";

export function AuditView() {
  const [range, setRange] = useState<AdminWindow>("30d");
  const [success, setSuccess] = useState<"" | "true" | "false">("");
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [draftAction, setDraftAction] = useState("");
  const [draftTargetType, setDraftTargetType] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AuditListData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminAudit({
          window: range,
          success: success === "" ? undefined : success === "true",
          action,
          targetType,
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
          setError("The administrative audit read model could not be loaded.");
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
  }, [range, success, action, targetType, page, refresh]);

  function applyFilters() {
    setLoading(true);
    setAction(draftAction.trim());
    setTargetType(draftTargetType.trim());
    setPage(1);
  }

  return (
    <div>
      <AdminPageHeader
        eyebrow="Audit log"
        title="Administrative audit trail"
        description="Append-oriented events for administrator actions and denied authenticated admin attempts. Unauthenticated denials remain in request logs because no trusted actor exists."
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
            Outcome
            <select
              value={success}
              onChange={(event) => {
                setLoading(true);
                setSuccess(event.target.value as "" | "true" | "false");
                setPage(1);
              }}
              className="ui-field w-auto py-2"
            >
              <option value="">All outcomes</option>
              <option value="true">Success</option>
              <option value="false">Failure</option>
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
            Action
            <input
              value={draftAction}
              onChange={(event) => setDraftAction(event.target.value)}
              placeholder="For example admin.access_denied"
              className="ui-field mt-1.5"
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Target type
            <input
              value={draftTargetType}
              onChange={(event) => setDraftTargetType(event.target.value)}
              placeholder="For example route"
              className="ui-field mt-1.5"
            />
          </label>
          <button type="submit" className="ui-button ui-button-secondary self-end">
            Apply filters
          </button>
        </form>
      </div>

      <div className="mt-6">
        {loading ? (
          <LoadingPanel label="Loading audit events…" />
        ) : error ? (
          <AdminErrorState
            title="Audit events unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        ) : data ? (
          <Panel
            title="Audit events"
            description={`${data.total.toLocaleString()} events in the selected window.`}
          >
            {data.items.length === 0 ? (
              <EmptyState
                title="No audit events found"
                message="No administrative audit events match the selected filters."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[840px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Time</th>
                      <th className="pb-3 pr-4 font-medium">Action</th>
                      <th className="pb-3 pr-4 font-medium">Actor</th>
                      <th className="pb-3 pr-4 font-medium">Target</th>
                      <th className="pb-3 pr-4 font-medium">Outcome</th>
                      <th className="pb-3 font-medium">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((event) => (
                      <tr
                        key={event.event_id}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="py-3 pr-4 text-muted">
                          {formatDateTime(event.created_at)}
                        </td>
                        <td className="py-3 pr-4 font-medium text-ink">
                          {event.action}
                        </td>
                        <td className="py-3 pr-4 font-mono text-xs text-muted">
                          {event.actor_user_id ?? "Unknown"}
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {event.target_type}
                          {event.target_id ? `: ${event.target_id}` : ""}
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                              event.success
                                ? "border-success/25 text-success"
                                : "border-danger/25 text-danger"
                            }`}
                          >
                            {event.success ? "Success" : "Failure"}
                          </span>
                        </td>
                        <td className="py-3 text-muted">
                          {event.reason ?? "None"}
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
