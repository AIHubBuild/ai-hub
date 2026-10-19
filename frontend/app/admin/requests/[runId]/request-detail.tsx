"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAdminRequest, type AdminRequestDetail } from "../../../lib/admin";
import {
  AdminErrorState,
  formatDateTime,
  formatLatency,
  LoadingPanel,
  Panel,
  StatusPill,
} from "../../components/admin-ui";

export function RequestDetail({ runId }: { runId: string }) {
  const [data, setData] = useState<AdminRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminRequest(runId);
        if (cancelled) {
          return;
        }
        setData(next);
        setError(null);
      } catch {
        if (!cancelled) {
          setError("The AI request could not be loaded. It may not exist in the selected data set.");
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
  }, [runId, refresh]);

  return (
    <div>
      <Link
        href="/admin/requests"
        className="inline-flex text-sm font-medium text-muted underline-offset-4 hover:text-ink hover:underline"
      >
        ← Back to AI requests
      </Link>

      <div className="mt-5">
        {loading ? (
          <LoadingPanel label="Loading request detail…" />
        ) : error ? (
          <AdminErrorState
            title="Request unavailable"
            message={error}
            onRetry={() => {
              setLoading(true);
              setRefresh((value) => value + 1);
            }}
          />
        ) : data ? (
          <div className="space-y-5">
            <header className="border-b border-line pb-6">
              <p className="ui-eyebrow">AI request</p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <h1 className="ui-display break-all text-2xl text-ink sm:text-3xl">
                  {data.run_id}
                </h1>
                <StatusPill status={data.status} />
              </div>
            </header>

            <Panel
              title="Request metadata"
              description="Safe operational fields only. Prompts, inputs, outputs, and raw exception messages are never returned."
            >
              <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <Detail label="Assistant" value={data.assistant} />
                <Detail label="Workflow" value={data.workflow_id} />
                <Detail label="Model" value={data.model ?? "Unknown"} />
                <Detail label="User ID" value={data.user_id} mono />
                <Detail label="Created" value={formatDateTime(data.created_at)} />
                <Detail label="Latency" value={formatLatency(data.latency_ms)} />
                <Detail
                  label="Error category"
                  value={data.error_category ?? "None"}
                />
                <Detail label="Prompt ID" value={data.prompt_id ?? "Unknown"} />
                <Detail
                  label="Prompt version"
                  value={
                    data.prompt_version === null
                      ? "Unknown"
                      : String(data.prompt_version)
                  }
                />
                <Detail label="Thread ID" value={data.thread_id ?? "None"} mono />
              </dl>
            </Panel>

            <div className="flex flex-wrap gap-3">
              <Link
                href={`/admin/users/${data.user_id}`}
                className="ui-button ui-button-secondary"
              >
                View user activity
              </Link>
              <Link
                href={`/admin/incidents?linked_run_id=${encodeURIComponent(
                  data.run_id,
                )}&linked_user_id=${encodeURIComponent(data.user_id)}`}
                className="ui-button ui-button-secondary"
              >
                Create incident from request
              </Link>
            </div>
          </div>
        ) : null}
      </div>
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
        className={`mt-1 break-all text-sm text-ink ${mono ? "font-mono text-xs" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
