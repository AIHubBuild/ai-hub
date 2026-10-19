# User Profiles and Signup

## Identity model

Supabase Auth remains the only authentication identity and password
store. The application does not create a local users table and does not
store passwords. Profile rows reference the Supabase user UUID directly.

## Schema

Migration `0009_user_profiles` adds `user_profiles`:

| Column | Purpose |
|---|---|
| `user_id` | Supabase user UUID, primary key |
| `full_name` | Required display name |
| `phone` | Optional validated phone number |
| `country_code` | Optional two-letter country code |
| `city` | Optional city for profile context |
| `career_goal` | Optional product preference |
| `marketing_consent` | Separate marketing opt-in, default false |
| `terms_accepted_at` / `terms_version` | Terms acceptance audit |
| `privacy_accepted_at` / `privacy_version` | Privacy acceptance audit |
| `created_at` / `updated_at` | Record timestamps |

No payment-card fields, billing addresses, or frontend-supplied
entitlement fields are stored. Future subscription ownership should
continue to use the Supabase user UUID and backend-verified entitlement
records.

## API

Authenticated self-service only:

```text
GET /api/v1/profile
PUT /api/v1/profile
```

- Ownership comes only from the verified JWT `sub`; `user_id` is rejected
  in request bodies.
- The API uses `require_verified_email`, so suspended and unverified accounts are denied.
- Profile creation requires Terms and Privacy acceptance.
- Updates require full-name validation and optional phone, country, and
  city validation.
- The response includes email and `email_verified`; email is not duplicated
  in the profile table. PostgreSQL confirmation state is checked in
  Supabase `auth.users.email_confirmed_at` when the JWT claim is absent.
- Passwords and access tokens are never written to profile records or logs.

## Signup and email verification

The production flow is email-first:

1. `POST` signup through Supabase Auth with email, password, and a fresh
   hCaptcha token.
2. If confirmation is required, show a pending screen with resend support.
   No profile row or protected application access is available yet.
3. The confirmation link redirects to `/auth/callback`. The client uses
   PKCE code exchange (`exchangeCodeForSession`) or token-hash verification
   when the Supabase email template supplies `token_hash`.
4. Only after the session reports a confirmed email does the user continue
   to `/register/complete`.
5. Complete registration collects full name, optional phone, country, city,
   career goal, and optional marketing consent. Terms and Privacy acceptance
   are required at this step.
6. The profile is saved through `PUT /api/v1/profile`; the backend checks
   verified email and account status independently.

- If a PKCE link is opened in a different browser/device, the verifier is
  unavailable. The callback shows a clear message and links back to sign-in
  and resend.
- For cross-device confirmation, the Supabase confirmation template can be
  changed to use `token_hash`, which the callback also verifies.
- Unverified emails are never treated as verified. Profile, ATS Resume
  Assistant, and IT Support endpoints all require verified email.
- Marketing consent is separate, optional, and unchecked by default.

## Row Level Security

On PostgreSQL, migration `0009` enables RLS on `user_profiles` and, when
Supabase `auth.uid()` and the `authenticated` role exist, creates:

- `user_profiles_select_own` — select only rows where `auth.uid() = user_id`

`authenticated` receives SELECT only; INSERT, UPDATE, and DELETE are
revoked, and `anon` is revoked. Profile writes go exclusively through the
authenticated FastAPI endpoints, so direct Supabase Data API writes cannot
bypass backend validation or acceptance timestamps. The backend uses a
privileged database connection and enforces ownership in code; RLS protects
direct Supabase client reads. RLS is skipped on SQLite for local development
and tests.

## Policies and legal review

Implementation pages exist at `/terms` and `/privacy`, and signup records
acceptance with policy version `2026-10-19`. The text is implementation
copy, not legal advice; legal review is required before production launch.

## Deployment requirements

1. Apply migration `0009_user_profiles` through Alembic using an approved
   migration process.
2. Confirm Supabase `auth.uid()` and the `authenticated` role exist.
3. Verify the single read-only RLS policy and the SELECT-only grant.
4. Configure Supabase Auth email confirmation and allowed redirect URLs:
   `https://www.aihubassist.com/auth/callback` and the local
   `http://localhost:3000/auth/callback` URL. Keep `/login` allowlisted for
   normal sign-in flows if desired.
5. Confirm the backend database role can read
   `auth.users.email_confirmed_at` for verification enforcement.
6. Keep the backend OpenAI provider configuration unchanged.
7. Do not provision or change administrators as part of profile rollout.

Rollback: restoring the pre-migration database backup is preferred.
`alembic downgrade 0008` drops `user_profiles` and its policies, so use it
only when profile data loss is approved.

## Required Supabase Auth settings and verification

Before production approval, verify in the Supabase Dashboard:

1. **Authentication → URL Configuration**
   - Site URL: `https://www.aihubassist.com`
   - Redirect URLs include `https://www.aihubassist.com/login`
   - If the apex domain is also used, add its matching `/login` URL
     explicitly. Do not use wildcard redirects.
2. **Authentication → Providers → Email**
   - Email confirmation is enabled for production.
   - The confirmation email template uses the approved redirect URL.
3. **Authentication → Policies / Password settings**
   - Minimum password length is at least 8 characters.
4. **Authentication → Users**
   - After a new signup, the user shows as unconfirmed until the email
     link is completed.
5. **Database permissions**
   - The backend database role can read
     `auth.users.email_confirmed_at` (verified in production).
   - RLS is enabled on `user_profiles`.
   - Only `user_profiles_select_own` exists.
   - `authenticated` has SELECT only; INSERT, UPDATE, and DELETE are
     revoked.
   - `anon` has no table access.

Verification sequence:

1. Sign up with a new address and verify the pending/resend screen appears.
2. Confirm that no profile row is created and protected ATS/Support/profile
   requests return HTTP 403 before confirmation.
3. Complete the confirmation email and verify the redirect lands on
   `/auth/callback`, then `/register/complete` only after verification.
4. Complete all required and optional profile fields and verify the profile
   is saved through the backend.
5. Verify an unconfirmed account receives HTTP 403 from `/api/v1/profile`,
   `/api/v1/resumes`, and `/api/v1/support/sessions`.
6. Verify a confirmed account receives HTTP 200 and only its own profile.
7. Using the Supabase Data API with a user JWT, verify direct SELECT returns
   only the user's row and direct INSERT/UPDATE are denied.
8. Verify service-role access remains backend-only and is never shipped to
   the frontend.
