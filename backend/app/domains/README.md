# Domains

AI Hub is a platform for multiple AI assistants. Each assistant will
live here as its own domain module, following the domain contract
defined in `docs/09_Migration_Analysis.md` (§3.3) and the API standards
in `docs/07_API_Design.md`.

## Existing domains

- `assistants/` — platform assistant catalogue (seed of the domain
  registry): static registry + `GET /api/v1/assistants`. Exposes the
  two public assistants (ATS Resume Assistant, AI IT Support Copilot)
  with their verified repository as a reference link. The AI Testing
  Framework is an internal tool and is intentionally excluded from the
  public catalogue. No hosted deployment URL is verified for any
  product, so no launch URLs are advertised.
- `resume_ats/` — Resume ATS domain (first migration target,
  `docs/09_Migration_Analysis.md` §5 Phase 2). Contains the
  deterministic keyword/scoring engine (ported per §3.2 KEEP), the
  six-section workflow contracts (`AtsAnalysisRequest` /
  `AtsAnalysisResult`), and the three versioned prompt assets for the
  approved analysis → tailored resume → cover letter workflow.
  Routers, the LangGraph workflow, and database models land in later
  slices.

## Future domains

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
