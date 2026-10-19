# Admin Incidents and Manual Entitlements

## Support incidents

Endpoints:

```text
GET   /api/v1/admin/incidents
POST  /api/v1/admin/incidents
GET   /api/v1/admin/incidents/{incident_id}
PATCH /api/v1/admin/incidents/{incident_id}
```

All endpoints require an active administrator.

Controlled values:

```text
priority: low, medium, high, critical
status:   open, investigating, waiting_for_information, resolved, closed
```

Rules:

- Resolving or closing requires a non-empty resolution summary.
- Linked AI request IDs are validated against `ai_run_records`.
- Assigned administrator IDs are validated against `admin_users`.
- Linked user IDs are stored as references; they are not verified through
  Supabase in Slice 2A.
- Incident creation and updates are audited in the same transaction.
- Failed update attempts for missing incidents, invalid assignees, or missing
  resolution summaries are recorded as failed audit events.
- Incident audit details never include the description or resolution summary.
- The detail view includes the incident's administrative history.

## Manual entitlements

Endpoints:

```text
GET /api/v1/admin/entitlements
GET /api/v1/admin/users/{user_id}/entitlement
PUT /api/v1/admin/users/{user_id}/entitlement
```

Rules:

- Source is always `manual`.
- Permitted tiers: `free`, `pro`.
- Optional `limits` must be a JSON object.
- A reason is required.
- No payment provider is integrated.
- Payment status is never inferred or fabricated.
- Every update is audited with old/new tier and whether limits changed.
- Limits and reasons are administrator-supplied operational metadata; do not
  put secrets or sensitive user content in them.

## Blocked account-management work

The following remain unavailable until backend-only Supabase Admin API access
is verified:

- User listing and search.
- Account details and email lookup.
- Suspension/reactivation with authoritative user verification.
- Session revocation.
- Account recovery.
- Account deletion execution.

Account deletion remains request-and-approval based; no irreversible deletion
is implemented.

## Migrations

New additive migrations:

```text
0004_admin_authorization
0005_admin_audit_actors
0006_ai_usage_indexes
0007_admin_incidents
0008_user_entitlements
0009_user_profiles
```

They have not been applied to the long-lived local database or production.
Local verification covers SQLite and an ephemeral PostgreSQL 14 cluster;
the production Supabase database has not been touched.

## Production database configuration

- Local development and tests may use SQLite.
- Staging, production, and `AI_DEPLOYMENT=true` require an explicit
  Supabase PostgreSQL URL using psycopg 3:

  ```text
  DATABASE_URL=postgresql+psycopg://<user>:<url-encoded-password>@<host>:5432/<database>?sslmode=require
  ```

- The backend validates this at startup; Alembic applies the same check.
  SQLite is rejected in deployment-like environments.
- Use the Supabase direct connection or session pooler for Alembic. Do
  not run migrations through a transaction pooler.
- Bare `postgresql://` and `postgres://` URLs are normalized to
  `postgresql+psycopg://`; other drivers are rejected.
- The existing SQLite file is not copied automatically. Preserving its
  data requires a separately approved export/import step before the
  service is switched to PostgreSQL.

## Production rollout checklist

Not executed as part of local Phase 2 verification.

1. Decide whether existing SQLite application data must be preserved. If
   yes, complete and verify an approved export/import before cutover.
2. In a maintenance window, back up the SQLite database and record its
   Alembic revision.
3. Configure the production environment file with the Supabase PostgreSQL
   URL, OpenAI provider, and Supabase auth settings. Do not print it.
4. Run `alembic current` against the target database, then
   `alembic upgrade head`; expect `0008`.
5. Provision the initial administrator with the verified Supabase user
   UUID through a privileged database session.
6. Start the backend and verify `/health` and `/ready`.
7. Verify a real administrator token against `/api/v1/admin/me`, and
   verify a non-admin token receives `403`.
8. Roll back by restoring the previous environment and backups. Do not
   rely on downgrades after production writes: `0005` can fail on denied
   access audit rows and `0006`–`0008` downgrades discard data.

Required checks before cutover:

```bash
systemctl show aihub-backend -p WorkingDirectory -p User
sqlite3 <SQLITE_DB_PATH> "SELECT version_num FROM alembic_version;"
sqlite3 <SQLITE_DB_PATH> "PRAGMA integrity_check;"
```

Backup before migration:

```bash
BACKUP_DIR=/var/backups/aihub/$(date +%Y%m%dT%H%M%S)
sudo mkdir -p "$BACKUP_DIR"
sudo cp --preserve=all <SQLITE_DB_PATH> "$BACKUP_DIR/aihub_dev.db"
sudo sha256sum "$BACKUP_DIR/aihub_dev.db"
```

Migration and verification:

```bash
cd <BACKEND_DIR>
set -a; . <ENV_FILE>; set +a
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic current
curl -fsS https://api.aihubassist.com/health
curl -fsS https://api.aihubassist.com/ready
```
