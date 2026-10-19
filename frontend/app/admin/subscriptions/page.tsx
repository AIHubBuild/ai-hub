"use client";

import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import {
  fetchAdminEntitlements,
  setAdminEntitlement,
  type EntitlementListData,
  type EntitlementTier,
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

export default function AdminSubscriptionsPage() {
  const [tier, setTier] = useState<EntitlementTier | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EntitlementListData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  const [userId, setUserId] = useState("");
  const [newTier, setNewTier] = useState<EntitlementTier>("free");
  const [limits, setLimits] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await fetchAdminEntitlements({
          tier,
          page,
          pageSize: 25,
        });
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("Manual entitlements could not be loaded.");
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
  }, [tier, page, refresh]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveError(null);
    setSaveNotice(null);

    let parsedLimits: Record<string, unknown> | null = null;
    if (limits.trim()) {
      try {
        const parsed = JSON.parse(limits) as unknown;
        if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
          throw new Error("Limits must be a JSON object.");
        }
        parsedLimits = parsed as Record<string, unknown>;
      } catch {
        setSaveError("Limits must be valid JSON object text.");
        return;
      }
    }

    setSaving(true);
    try {
      await setAdminEntitlement(userId.trim(), {
        tier: newTier,
        limits: parsedLimits,
        reason: reason.trim(),
      });
      setUserId("");
      setLimits("");
      setReason("");
      setSaveNotice("Manual entitlement saved.");
      setLoading(true);
      setRefresh((value) => value + 1);
    } catch (caught) {
      setSaveError(
        caught instanceof ApiError
          ? caught.message
          : "The manual entitlement could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <AdminPageHeader
        eyebrow="Subscriptions"
        title="Manual entitlements"
        description="Manual operational grants only. There is no payment provider integration, and no payment status is inferred or fabricated."
      />

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel
          title="Grant or update manual entitlement"
          description="Valid tiers: free or pro. Limits are optional JSON metadata for operational planning."
        >
          <form onSubmit={save} className="space-y-3">
            <label className="block text-xs font-medium text-muted">
              Supabase user UUID
              <input
                required
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                className="ui-field mt-1.5 font-mono text-xs"
              />
            </label>
            <label className="block text-xs font-medium text-muted">
              Tier
              <select
                value={newTier}
                onChange={(event) =>
                  setNewTier(event.target.value as EntitlementTier)
                }
                className="ui-field mt-1.5"
              >
                <option value="free">free</option>
                <option value="pro">pro</option>
              </select>
            </label>
            <label className="block text-xs font-medium text-muted">
              Limits JSON (optional)
              <textarea
                rows={4}
                value={limits}
                onChange={(event) => setLimits(event.target.value)}
                placeholder={'{"monthly_requests": 100}'}
                className="ui-field mt-1.5 font-mono text-xs"
              />
            </label>
            <label className="block text-xs font-medium text-muted">
              Reason
              <input
                required
                minLength={3}
                maxLength={1000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="ui-field mt-1.5"
              />
            </label>
            {saveError ? (
              <p role="alert" className="text-xs text-danger">
                {saveError}
              </p>
            ) : null}
            {saveNotice ? (
              <p className="text-xs text-success">{saveNotice}</p>
            ) : null}
            <button
              type="submit"
              disabled={saving}
              className="ui-button ui-button-primary"
            >
              {saving ? "Saving…" : "Save entitlement"}
            </button>
          </form>
        </Panel>

        <Panel
          title="Manual entitlement records"
          description={`${data?.total ?? 0} records. Source is always manual; payment status is not tracked.`}
        >
          <label className="mb-4 flex items-center gap-2 text-xs font-medium text-muted">
            Tier
            <select
              value={tier}
              onChange={(event) => {
                setLoading(true);
                setTier(event.target.value as EntitlementTier | "");
                setPage(1);
              }}
              className="ui-field w-auto py-2"
            >
              <option value="">All tiers</option>
              <option value="free">free</option>
              <option value="pro">pro</option>
            </select>
          </label>

          {loading ? (
            <LoadingPanel label="Loading manual entitlements…" />
          ) : error ? (
            <AdminErrorState
              title="Entitlements unavailable"
              message={error}
              onRetry={() => {
                setLoading(true);
                setRefresh((value) => value + 1);
              }}
            />
          ) : data && data.items.length === 0 ? (
            <EmptyState
              title="No manual entitlements"
              message="No manual entitlement records match the selected filter."
            />
          ) : data ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-[0.1em] text-muted">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">User</th>
                      <th className="pb-3 pr-4 font-medium">Tier</th>
                      <th className="pb-3 pr-4 font-medium">Limits</th>
                      <th className="pb-3 pr-4 font-medium">Reason</th>
                      <th className="pb-3 font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => (
                      <tr
                        key={item.user_id}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="py-3 pr-4 font-mono text-xs text-muted">
                          {item.user_id}
                        </td>
                        <td className="py-3 pr-4 font-medium text-ink">
                          {item.tier}
                        </td>
                        <td className="max-w-52 truncate py-3 pr-4 text-muted">
                          {item.limits
                            ? JSON.stringify(item.limits)
                            : "No explicit limits"}
                        </td>
                        <td className="max-w-56 truncate py-3 pr-4 text-muted">
                          {item.reason}
                        </td>
                        <td className="py-3 text-muted">
                          {formatDateTime(item.updated_at)}
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
