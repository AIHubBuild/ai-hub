"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import {
  createAdminIncident,
  fetchAdminIncidents,
  type IncidentListData,
  type IncidentPriority,
  type IncidentStatus,
} from "../../lib/admin";
import {
  AdminErrorState,
  AdminPageHeader,
  EmptyState,
  formatDateTime,
  LoadingPanel,
  Pagination,
  Panel,
} from "../components/admin-ui";

const INCIDENT_STATUSES: IncidentStatus[] = [
  "open",
  "investigating",
  "waiting_for_information",
  "resolved",
  "closed",
];

const INCIDENT_PRIORITIES: IncidentPriority[] = [
  "low",
  "medium",
  "high",
  "critical",
];

function label(value: string): string {
  return value.replaceAll("_", " ");
}

function statusClass(status: IncidentStatus): string {
  if (status === "resolved" || status === "closed") {
    return "border-success/25 text-success";
  }
  if (status === "waiting_for_information") {
    return "border-line text-muted";
  }
  return "border-accent/25 text-accent";
}

function priorityClass(priority: IncidentPriority): string {
  if (priority === "critical" || priority === "high") {
    return "border-danger/25 text-danger";
  }
  return "border-line text-muted";
}

export function IncidentsView({
  initialLinkedRunId = "",
  initialLinkedUserId = "",
}: {
  initialLinkedRunId?: string;
  initialLinkedUserId?: string;
} = {}) {
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [priority, setPriority] = useState<IncidentPriority | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<IncidentListData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("platform");
  const [newPriority, setNewPriority] =
    useState<IncidentPriority>("medium");
  const [linkedUserId, setLinkedUserId] = useState(initialLinkedUserId);
  const [linkedRunId, setLinkedRunId] = useState(initialLinkedRunId);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createNotice, setCreateNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminIncidents({
          status,
          priority,
          page,
          pageSize: 25,
        });
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("Support incidents could not be loaded.");
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
  }, [status, priority, page, refresh]);

  async function createIncident(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    setCreateNotice(null);
    try {
      await createAdminIncident({
        title,
        description,
        category,
        priority: newPriority,
        linked_user_id: linkedUserId.trim() || null,
        linked_run_id: linkedRunId.trim() || null,
      });
      setTitle("");
      setDescription("");
      setCategory("platform");
      setNewPriority("medium");
      setLinkedUserId("");
      setLinkedRunId("");
      setCreateNotice("Incident created.");
      setLoading(true);
      setRefresh((value) => value + 1);
    } catch (caught) {
      setCreateError(
        caught instanceof ApiError
          ? caught.message
          : "The incident could not be created.",
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <AdminPageHeader
        eyebrow="Incidents"
        title="Support incident tracking"
        description="Internal operational incidents linked to users or AI request IDs. All changes are authorized by the backend and audited."
      />

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel
          title="Create incident"
          description="Do not include secrets, raw prompts, resumes, or full support conversations."
        >
          <form onSubmit={createIncident} className="space-y-3">
            <label className="block text-xs font-medium text-muted">
              Title
              <input
                required
                minLength={3}
                maxLength={200}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="ui-field mt-1.5"
              />
            </label>
            <label className="block text-xs font-medium text-muted">
              Description
              <textarea
                required
                maxLength={10000}
                rows={4}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="ui-field mt-1.5"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-xs font-medium text-muted">
                Category
                <input
                  required
                  maxLength={64}
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="ui-field mt-1.5"
                />
              </label>
              <label className="block text-xs font-medium text-muted">
                Priority
                <select
                  value={newPriority}
                  onChange={(event) =>
                    setNewPriority(event.target.value as IncidentPriority)
                  }
                  className="ui-field mt-1.5"
                >
                  {INCIDENT_PRIORITIES.map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-xs font-medium text-muted">
                Linked user ID (optional)
                <input
                  value={linkedUserId}
                  onChange={(event) => setLinkedUserId(event.target.value)}
                  className="ui-field mt-1.5 font-mono text-xs"
                />
              </label>
              <label className="block text-xs font-medium text-muted">
                Linked request ID (optional)
                <input
                  value={linkedRunId}
                  onChange={(event) => setLinkedRunId(event.target.value)}
                  className="ui-field mt-1.5 font-mono text-xs"
                />
              </label>
            </div>
            {createError ? (
              <p role="alert" className="text-xs text-danger">
                {createError}
              </p>
            ) : null}
            {createNotice ? (
              <p className="text-xs text-success">{createNotice}</p>
            ) : null}
            <button
              type="submit"
              disabled={creating}
              className="ui-button ui-button-primary"
            >
              {creating ? "Creating…" : "Create incident"}
            </button>
          </form>
        </Panel>

        <Panel
          title="Incident queue"
          description={`${data?.total ?? 0} incidents match the selected filters.`}
        >
          <div className="mb-4 flex flex-wrap gap-3">
            <label className="flex items-center gap-2 text-xs font-medium text-muted">
              Status
              <select
                value={status}
                onChange={(event) => {
                  setLoading(true);
                  setStatus(event.target.value as IncidentStatus | "");
                  setPage(1);
                }}
                className="ui-field w-auto py-2"
              >
                <option value="">All statuses</option>
                {INCIDENT_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {label(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-xs font-medium text-muted">
              Priority
              <select
                value={priority}
                onChange={(event) => {
                  setLoading(true);
                  setPriority(event.target.value as IncidentPriority | "");
                  setPage(1);
                }}
                className="ui-field w-auto py-2"
              >
                <option value="">All priorities</option>
                {INCIDENT_PRIORITIES.map((value) => (
                  <option key={value} value={value}>
                    {label(value)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loading ? (
            <LoadingPanel label="Loading incidents…" />
          ) : error ? (
            <AdminErrorState
              title="Incidents unavailable"
              message={error}
              onRetry={() => {
                setLoading(true);
                setRefresh((value) => value + 1);
              }}
            />
          ) : data && data.items.length === 0 ? (
            <EmptyState
              title="No incidents found"
              message="No support incidents match the selected filters."
            />
          ) : data ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Incident</th>
                      <th className="pb-3 pr-4 font-medium">Status</th>
                      <th className="pb-3 pr-4 font-medium">Priority</th>
                      <th className="pb-3 pr-4 font-medium">Category</th>
                      <th className="pb-3 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((incident) => (
                      <tr
                        key={incident.incident_id}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="py-3 pr-4">
                          <Link
                            href={`/admin/incidents/${incident.incident_id}`}
                            className="font-medium text-ink underline-offset-4 hover:underline"
                          >
                            {incident.title}
                          </Link>
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusClass(incident.status)}`}
                          >
                            {label(incident.status)}
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${priorityClass(incident.priority)}`}
                          >
                            {label(incident.priority)}
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-muted">
                          {incident.category}
                        </td>
                        <td className="py-3 text-muted">
                          {formatDateTime(incident.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={data.page}
                totalPages={data.total_pages}
                onPageChange={(next) => {
                  setLoading(true);
                  setPage(next);
                }}
              />
            </>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
