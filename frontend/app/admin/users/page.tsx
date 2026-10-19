"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AdminPageHeader,
  EmptyState,
  Panel,
} from "../components/admin-ui";

export default function AdminUsersPage() {
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function openUserActivity(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = userId.trim();
    if (!value) {
      setError("Enter a Supabase user ID.");
      return;
    }
    setError(null);
    router.push(`/admin/users/${encodeURIComponent(value)}`);
  }

  return (
    <div>
      <AdminPageHeader
        eyebrow="Users"
        title="User management is not available yet"
        description="User listing, account details, suspension, reactivation, recovery, session revocation, and deletion require verified backend-only Supabase Admin API access. No account data is shown or fabricated here."
      />

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel
          title="Account directory unavailable"
          description="The backend does not currently expose a user list or account-detail endpoint."
        >
          <EmptyState
            title="No user directory"
            message="This page will remain read-only and unavailable until backend-only Supabase administrative access is configured and verified. Suspension and other account actions are disabled."
          />
        </Panel>

        <Panel
          title="User activity by ID"
          description="This uses the existing AI request read model and does not expose account details."
        >
          <form onSubmit={openUserActivity} className="space-y-3">
            <label className="block text-xs font-medium text-muted">
              Supabase user UUID
              <input
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="550e8400-e29b-41d4-a716-446655440000"
                className="ui-field mt-1.5 font-mono text-xs"
              />
            </label>
            {error ? (
              <p role="alert" className="text-xs text-danger">
                {error}
              </p>
            ) : null}
            <button type="submit" className="ui-button ui-button-secondary">
              Open activity
            </button>
          </form>
          <p className="mt-3 text-xs leading-5 text-muted">
            Only AI request activity for the provided ID is shown. No email,
            subscription, or account status is invented.
          </p>
        </Panel>
      </div>
    </div>
  );
}
