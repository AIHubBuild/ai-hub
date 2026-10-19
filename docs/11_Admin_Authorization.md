# Admin Authorization and Account Status (Phase 2, Milestone 1)

## Scope

This milestone adds database-backed administrator authorization and
account suspension enforcement. It does not add user-management APIs or
the admin dashboard yet.

## Models

Migration `0004_admin_authorization` adds:

- `admin_users` — trusted administrator identities keyed by Supabase
  user UUID.
- `user_account_status` — `active` or `suspended` account state.
- `admin_audit_events` — append-oriented administrative audit events.

No existing tables are altered. The migration is additive and reversible.

## Initial administrator provisioning

There is no public promotion endpoint. Provision the initial
administrator manually with the user's Supabase UUID:

```sql
INSERT INTO admin_users (user_id, created_at, created_by)
VALUES ('<supabase-user-uuid>', CURRENT_TIMESTAMP, NULL);
```

Use a privileged database migration/administration session. Do not add
an automatic first-user rule and do not expose this operation through
the public API.

## Authorization behavior

- `GET /api/v1/admin/me` requires:
  - a valid Supabase JWT
  - an active account
  - a row in `admin_users`
- Unauthenticated requests return `401`.
- Authenticated non-admin or suspended users return `403`.
- Ordinary users cannot promote themselves or assign roles.

## Suspension behavior

`get_active_user()` is used by protected Resume ATS and IT Support
Copilot endpoints. A `user_account_status.status = 'suspended'` row
returns `403` before domain logic or AI calls run.

A missing status row is treated as active for backward compatibility.
Suspending a user does not claim to revoke existing Supabase sessions.

### Account-status lookup performance

Every protected request performs one primary-key lookup against
`user_account_status`. The lookup is indexed by `user_id`, adds one
database round trip, and intentionally is not cached so suspension
takes effect on the next request. If profiling shows this is material,
a short-TTL cache with explicit invalidation can be evaluated later;
immediate enforcement takes priority over that optimization.

## Audit events

`add_admin_audit_event()` participates in the caller's transaction and
is the required helper for privileged database mutations. The business
change and its audit event must commit together.

`record_admin_audit_event()` commits immediately and is used only for
standalone events such as denied authenticated administrator access,
where there is no corresponding business mutation to keep atomic.

Authenticated non-admin and suspended-admin denials create failed audit
events. Unauthenticated denials have no trusted actor and remain in
metadata-only request logs with request ID, route, and status.

Audit records are append-oriented. They are not exposed for editing.
Audit details must contain only safe metadata; never secrets, tokens,
headers, prompts, resumes, job descriptions, support conversations, or
raw exception messages.

## Production notes

- Do not run migration `0004` against production until the production
  database type, current revision, backup, and migration process are
  verified and approved.
- This milestone does not require a Supabase service-role key.
- User-management operations that require Supabase Admin API access
  remain blocked until a backend-only `SUPABASE_SERVICE_ROLE_KEY` is
  available.
