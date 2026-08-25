# Domains

AI Hub is a platform for multiple AI assistants. Each assistant will
live here as its own domain module, following the domain contract
defined in `docs/09_Migration_Analysis.md` (§3.3) and the API standards
in `docs/07_API_Design.md`.

No domains exist yet. Future modules include:

- Resume ATS
- IT Support Copilot
- AI Testing / Evaluation (future integration point)
- Career Coach
- Interview Coach
- Job Matching
- Other AI assistants

A new domain package is expected to expose:

1. Pydantic schemas — request/response models for its API.
2. APIRouter(s) — mounted by `app/api/router.py`.
3. Service layer — the domain's business logic.
4. Optional LangGraph workflow(s) — registered with the shared AI core
   (to be built in a later phase).
5. Prompt assets — versioned prompts.
6. DB models/migrations — owned by the domain, applied through the
   shared Alembic baseline (to be added in a later phase).

Adding a new assistant must require only a new package here plus its
frontend routes — no changes to the platform core.
