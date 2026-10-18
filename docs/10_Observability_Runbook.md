# Observability and Recovery Runbook (Phase 1A)

Scope: the FastAPI backend (`aihub-backend`) on the Contabo VPS. This
runbook is operational guidance only. Commands marked **read-only** are
safe to inspect; recovery actions require explicit approval.

## 1. Health and readiness

| Endpoint | Purpose | Expected |
|---|---|---|
| `GET /health` | Liveness: process is serving requests | `200` with `status: ok` |
| `GET /ready` | Readiness: database answers `SELECT 1` | `200` when healthy, `503` when the database is unavailable |
| `GET /api/v1/health` | Versioned liveness | `200` |
| `GET /api/v1/ready` | Versioned readiness | `200` / `503` |

`/health` deliberately does not call the database or OpenAI. Do not add
provider calls to health checks: they add cost, latency, and rate-limit
risk.

Both endpoints return `Cache-Control: no-store` and an `X-Request-ID`
header.

### Uptime monitoring

Configure an external monitor (UptimeRobot, Better Stack, or equivalent)
to request:

```text
https://api.aihubassist.com/health
```

every 1–5 minutes, alerting after two consecutive failures. Use `/ready`
for deployment verification and lower-frequency database checks, not for
high-frequency polling.

## 2. Read-only systemd verification

Run these on the VPS after approval. Do not change the unit during
verification.

```bash
systemctl status aihub-backend --no-pager
systemctl show aihub-backend \
  -p FragmentPath -p WorkingDirectory -p ExecStart -p User \
  -p Restart -p RestartUSec -p NRestarts
systemd-analyze verify /etc/systemd/system/aihub-backend.service
```

Do not print the full unit file, environment values, or environment-file
contents; those can expose secrets. If `ExecStart` contains sensitive
command-line arguments, redact them before sharing the output.

Verify:

- `Restart=on-failure` (or an explicitly chosen restart policy).
- A sensible `RestartSec` (for example 5–10 seconds).
- Start-limit settings do not hide a crash loop.
- `ExecStart` points at the intended uvicorn command and virtualenv.
- The service runs as the intended non-root user.

Check restart behavior:

```bash
systemctl show aihub-backend -p NRestarts
journalctl -u aihub-backend --since "24 hours ago" --no-pager \
  | grep -E "Started|Stopped|Failed|Scheduled restart"
```

Do not print or copy the unit file if it contains inline `Environment=`
values. Use only the safe `systemctl show` properties above. Do not edit
the unit as part of this phase.

## 3. Read-only journald verification

```bash
journalctl --disk-usage
journalctl -u aihub-backend -p err --since "24 hours ago" --no-pager
journalctl -u aihub-backend --since "24 hours ago" --no-pager
grep -E "^(Storage|SystemMaxUse|MaxRetentionSec|RuntimeMaxUse)" \
  /etc/systemd/journald.conf
```

Recommendations (apply only with approval):

- Persist logs across reboots (`Storage=persistent`).
- Bound disk usage (`SystemMaxUse=1G` or similar).
- Retain at least 14–30 days (`MaxRetentionSec=30d`).

Application logs are metadata-only. They must never contain prompts,
model responses, resume text, support messages, query strings,
authorization headers, API keys, or other secrets.

## 4. Crash and failure detection

| Signal | Where |
|---|---|
| Process unavailable | External uptime monitor on `/health` |
| Database unavailable | `/ready` returns `503`; readiness warning log |
| Unexpected restart | `systemctl show -p NRestarts`; journald restart lines |
| Unhandled exception | `unhandled_exception ... request_id=... exc_type=... message=[redacted]` |
| AI workflow failure | `ai_workflow_failed workflow_id=... domain=... run_id=... error_type=...` |
| HTTP 5xx / slow requests | `request method=... path=... status=... duration_ms=... request_id=...` |

Use the `X-Request-ID` response header to correlate a client report with
the matching server log line. Never ask users to send prompts or
credentials for correlation.

## 5. Recovery procedure

1. Confirm the alert source (uptime monitor, user report, or readiness
   check).
2. Check liveness and readiness:
   ```bash
   curl -i https://api.aihubassist.com/health
   curl -i https://api.aihubassist.com/ready
   ```
3. Inspect the service:
   ```bash
   systemctl status aihub-backend --no-pager
   journalctl -u aihub-backend -n 200 --no-pager
   ```
4. If the process is stopped, restart only with approval:
   ```bash
   sudo systemctl restart aihub-backend
   ```
5. Verify recovery:
   ```bash
   curl -i https://api.aihubassist.com/health
   curl -i https://api.aihubassist.com/ready
   systemctl status aihub-backend --no-pager
   ```
6. If `/ready` is `503`, treat it as a database/Supabase issue. Check the
   Supabase project status and network reachability. Do not reset,
   delete, or recreate the production database.
7. If AI requests return `502`/`503`, inspect recent `ai_run_records`
   rows and logs. Confirm the configured provider is OpenAI. Do not
   switch the production provider to DeepSeek.
8. Record the incident time, request id(s), affected endpoint(s), and
   recovery action in the operations log.

## 6. Read-only AI run-record queries

Use the Supabase SQL editor or a read-only role. Adjust the interval as
needed.

```sql
-- Failure count by assistant in the last 24 hours
SELECT domain, workflow_id, count(*) AS failures
FROM ai_run_records
WHERE status = 'error'
  AND created_at >= now() - interval '24 hours'
GROUP BY domain, workflow_id
ORDER BY failures DESC;

-- Slowest recent runs
SELECT run_id, domain, workflow_id, model, latency_ms, created_at
FROM ai_run_records
WHERE created_at >= now() - interval '24 hours'
ORDER BY latency_ms DESC
LIMIT 20;

-- Error types (first segment of the stored error text)
SELECT domain, split_part(error, ':', 1) AS error_type, count(*) AS count
FROM ai_run_records
WHERE status = 'error'
  AND created_at >= now() - interval '24 hours'
GROUP BY domain, error_type
ORDER BY count DESC;
```

These queries may scan if volume grows; add indexes only after an
approved dashboard or scheduled query exists.

## 7. Logs vs. future admin dashboard

Server logs belong here:

- Request method, path, status, duration, request id.
- Exception type and redacted message.
- AI workflow id, domain, run id, error type, latency.
- Restart and readiness events.

A future secure admin dashboard may show aggregate, read-only data:

- Failure rate by assistant.
- p95 latency by endpoint/workflow.
- Token usage and estimated cost (future phase).
- Ticket/session counts.

It must never expose raw `input_state`, `output_state`, prompts, resumes,
support conversations, user identifiers beyond operational need, or
secrets without explicit authorization and retention controls.

## 8. Known limitations in Phase 1A

- No token usage columns, migrations, Sentry, or admin dashboard.
- No VPS access was used for this phase; the systemd and journald checks
  above must be run on the server after approval.
- No production configuration was changed.
