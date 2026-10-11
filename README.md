# AI Hub

**A platform where AI assistants work together.**

AI Hub is not a single-purpose AI application. It is a unified platform
designed to host multiple AI assistants — Resume ATS, IT Support Copilot,
Career Coach, Interview Coach, Job Matching, and future AI agents — as
pluggable modules on one shared foundation.

> Status: **Platform foundation + assistant catalogue + Resume ATS +
> IT Support Copilot + authentication.**
> The Next.js + FastAPI scaffold is in place. The assistant catalogue is
> implemented end-to-end, and the first two assistants are integrated:
> - **ATS Resume Assistant** — resume upload (PDF/DOCX/TXT, 5 MB limit),
>   ATS analysis via the deterministic keyword engine plus an AI provider
>   (OpenAI-compatible, configured with `OPENAI_API_KEY`), run-record
>   persistence, and tailored-resume DOCX download.
> - **AI IT Support Copilot** — issue classification, knowledge-base
>   troubleshooting, ticket lifecycle, escalation, and root-cause
>   summaries, with persisted sessions and tickets.
> Authentication uses Supabase Auth: the backend validates Supabase-issued
> JWTs on all assistant endpoints and enforces per-user isolation.
> Requires a Supabase project (`SUPABASE_JWT_SECRET` on the backend,
> `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` on the
> frontend). User profiles, Supabase Storage, and the remaining
> assistants (Career Coach, …) have not been built yet.

The detailed product and technical blueprint lives in [`docs/`](docs/) —
those documents are the primary source of truth for the platform.

---

## Architecture (high level)

```text
                    AI HUB PLATFORM
                         │
          ┌──────────────┼──────────────┐
          │              │              │
      Core Platform   AI Services   Domain Modules
          │              │              │
      Users           AI Core      Future assistants
      Auth            LangGraph    (Resume ATS, IT Support,
      Profiles        Models       Career Coach, ...)
      Settings        Evaluation
      Navigation
```

- **Frontend:** Next.js (React, TypeScript, Tailwind CSS) — one shell with per-assistant routes.
- **Backend:** FastAPI (Python) — modular monolith with a pluggable domain
  contract (`backend/app/domains/`).
- **Future services** (not yet implemented): PostgreSQL (Supabase), Supabase
  Auth/Storage, LangGraph + OpenAI, AWS/Terraform, Vercel deployment, CI/CD.

The platform-first rule: assistants are **consumers** of AI Hub. Adding a
new assistant must not require restructuring the platform
(see `docs/09_Migration_Analysis.md` §3.3).

---

## Repository Structure

```text
AI-Hub-New/
├── frontend/        # Next.js application
│   └── app/
│       ├── page.tsx           # dashboard (assistant catalogue)
│       ├── assistants/        # per-assistant detail routes
│       ├── components/        # shared UI components
│       └── lib/               # API client helpers
├── backend/         # FastAPI application
│   └── app/
│       ├── main.py          # app factory + health check
│       ├── core/            # configuration
│       ├── api/             # routing structure (api/v1)
│       └── domains/         # pluggable assistant domains
│           └── assistants/  # assistant catalogue (first domain)
├── docs/            # product & architecture documentation (source of truth)
├── .env.example     # environment variable template (no real secrets)
├── .gitignore
└── README.md
```

---

## Running Locally

### Prerequisites

- Node.js 18+ (recommended: current LTS)
- Python 3.10+

### Environment Variables

```bash
cp .env.example .env           # local development settings
cp .env.example frontend/.env.local   # Next.js reads env from here
```

No real secrets are required for the foundation. Real keys (Supabase,
OpenAI, etc.) will be configured in later phases and must never be
committed.

### Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Health check: http://localhost:8000/health
- Versioned health: http://localhost:8000/api/v1/health
- OpenAPI docs: http://localhost:8000/docs

### Backend Tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000

---

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/README.md` | Documentation index |
| `docs/01_Product_Vision_Document.md` … `docs/08_Implementation_Roadmap.md` | Product & architecture blueprint |
| `docs/09_Migration_Analysis.md` | Analysis of the legacy AI apps and migration plan |

Follow the development rule in `docs/08_Implementation_Roadmap.md` for
every future feature: define → design → build backend → build AI logic →
build frontend → test → security check → document → review → deploy.
