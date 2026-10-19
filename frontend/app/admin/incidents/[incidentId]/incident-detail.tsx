"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAdminIncident,
  updateAdminIncident,
  type AdminIncidentDetail,
  type IncidentPriority,
  type IncidentStatus,
} from "../../../lib/admin";
import {
  AdminErrorState,
  formatDateTime,
  LoadingPanel,
  Panel,
} from "../../components/admin-ui";

const STATUSES: IncidentStatus[] = [
  "open",
  "investigating",
  "waiting_for_information",
  "resolved",
  "closed",
];
const PRIORITIES: IncidentPriority[] = [
  "low",
  "medium",
  "high",
  "critical",
];

function label(value: string): string {
  return value.replaceAll("_", " ");
}

export function IncidentDetail({ incidentId }: { incidentId: string }) {
  const [incident, setIncident] = useState<AdminIncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  const [status, setStatus] = useState<IncidentStatus>("open");
  const [priority, setPriority] = useState<IncidentPriority>("medium");
  const [assignedAdmin, setAssignedAdmin] = useState("");
  const [resolution, setResolution] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminIncident(incidentId);
        if (cancelled) {
          return;
        }
        setIncident(next);
        setStatus(next.status);
        setPriority(next.priority);
        setAssignedAdmin(next.assigned_admin_id ?? "");
        setResolution(next.resolution_summary ?? "");
        setError(null);
      } catch {
        if (!cancelled) {
          setError("The support incident could not be loaded.");
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
  }, [incidentId, refresh]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      await updateAdminIncident(incidentId, {
        status,
        priority,
        assigned_admin_id: assignedAdmin.trim() || null,
        resolution_summary: resolution.trim() || null,
      });
      setLoading(true);
      setRefresh((value) => value + 1);
    } catch {
      setSaveError(
        "The incident could not be updated. Resolving or closing requires a resolution summary.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <Link
        href="/admin/incidents"
        className="inline-flex text-sm font-medium text-muted underline-offset-4 hover:text-ink hover:underline"
      >
        ← Back to incidents
      </Link>

      {loading ? (
        <div className="mt-6">
          <LoadingPanel label="Loading support incident…" />
        </div>
      ) : error ? (
        <div className="mt-6">
          <AdminErrorState
            title="Incident unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        </div>
      ) : incident ? (
        <div className="mt-5 space-y-5">
          <header className="border-b border-line pb-6">
            <p className="ui-eyebrow">Support incident</p>
            <h1 className="ui-display mt-3 text-2xl text-ink sm:text-3xl">
              {incident.title}
            </h1>
            <p className="mt-2 text-xs text-muted">
              Created {formatDateTime(incident.created_at)} · Updated{" "}
              {formatDateTime(incident.updated_at)}
            </p>
          </header>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Panel title="Incident details">
              <dl className="space-y-4 text-sm">
                <Detail label="Description" value={incident.description} />
                <Detail label="Category" value={incident.category} />
                <Detail
                  label="Linked user ID"
                  value={incident.linked_user_id ?? "None"}
                  mono
                />
                <Detail
                  label="Linked request ID"
                  value={incident.linked_run_id ?? "None"}
                  mono
                />
                <Detail
                  label="Resolution summary"
                  value={incident.resolution_summary ?? "Not resolved"}
                />
              </dl>
            </Panel>

            <Panel title="Update incident">
              <form onSubmit={save} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-xs font-medium text-muted">
                    Status
                    <select
                      value={status}
                      onChange={(event) =>
                        setStatus(event.target.value as IncidentStatus)
                      }
                      className="ui-field mt-1.5"
                    >
                      {STATUSES.map((value) => (
                        <option key={value} value={value}>
                          {label(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-xs font-medium text-muted">
                    Priority
                    <select
                      value={priority}
                      onChange={(event) =>
                        setPriority(event.target.value as IncidentPriority)
                      }
                      className="ui-field mt-1.5"
                    >
                      {PRIORITIES.map((value) => (
                        <option key={value} value={value}>
                          {label(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="block text-xs font-medium text-muted">
                  Assigned admin ID
                  <input
                    value={assignedAdmin}
                    onChange={(event) => setAssignedAdmin(event.target.value)}
                    className="ui-field mt-1.5 font-mono text-xs"
                  />
                </label>
                <label className="block text-xs font-medium text-muted">
                  Resolution summary
                  <textarea
                    rows={4}
                    maxLength={10000}
                    value={resolution}
                    onChange={(event) => setResolution(event.target.value)}
                    className="ui-field mt-1.5"
                  />
                </label>
                {saveError ? (
                  <p role="alert" className="text-xs text-danger">
                    {saveError}
                  </p>
                ) : null}
                <button
                  type="submit"
                  disabled={saving}
                  className="ui-button ui-button-primary"
                >
                  {saving ? "Saving…" : "Save incident"}
                </button>
              </form>
            </Panel>
          </div>

          <Panel
            title="Audit history"
            description="Administrative changes and failed update attempts for this incident."
          >
            {incident.history.length === 0 ? (
              <p className="text-sm text-muted">No history recorded.</p>
            ) : (
              <ul className="space-y-3">
                {incident.history.map((event) => (
                  <li
                    key={event.event_id}
                    className="border-b border-line/60 pb-3 text-sm last:border-0 last:pb-0"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink">
                        {event.action}
                      </span>
                      <span
                        className={`text-xs ${
                          event.success ? "text-success" : "text-danger"
                        }`}
                      >
                        {event.success ? "Success" : "Failure"}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      {formatDateTime(event.created_at)} ·{" "}
                      {event.actor_user_id ?? "Unknown actor"}
                      {event.reason ? ` · ${event.reason}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      ) : null}
    </div>
  );
}

function Detail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {label}
      </dt>
      <dd
        className={`mt-1 whitespace-pre-wrap break-words text-ink ${
          mono ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
