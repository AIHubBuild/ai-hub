# AI Hub Platform

# Migration Analysis: ATS Resume Assistant & AI IT Support Copilot

| Document | AI Hub Platform – Migration Analysis |
|----------|-------------------------------------|
| Version | 1.0 |
| Status | Draft |
| Product | AI Hub Platform |
| Author | Abiola Akinselure |
| Date | August 2026 |

---

# 1. Purpose

This document records the findings of a code-level analysis of the two existing Streamlit applications that AI Hub will absorb first:

- **ATS Resume Assistant** — https://github.com/akinselureabiola/ATS-Resume-Assistant
- **AI IT Support Copilot** — https://github.com/akinselureabiola/AI-IT-Support-Copilot

It identifies what exists, what is reusable, what must be replaced, and how each module maps from the current Streamlit architecture to the target Next.js + FastAPI architecture. It closes with a proposed repository layout and implementation sequence.

## 1.1 Platform Context

AI Hub is **not** a single-purpose resume application. It is a unified platform intended to host multiple AI applications. The first applications being migrated are:

1. ATS Resume Assistant (now)
2. AI IT Support Copilot (now)

Future applications are planned, including:

3. AI Career Coach
4. Interview Coach
5. Job Matching and other AI assistants

The architecture must therefore avoid coupling AI Hub to any single AI application. New AI domains/agents must be addable without restructuring the platform.

## 1.2 Future Architectural Dependency — AI Testing Framework

A separate repository exists: https://github.com/akinselureabiola/AI-Testing-Framework

- It is currently **unfinished** and is **NOT** migrated or integrated at this stage.
- **No assumptions are made about its current implementation.**
- It is treated as a **future architectural dependency**: a shared AI evaluation/testing layer capable of testing multiple AI applications and agents.
- The target architecture in this document reserves integration points for it (see §3.4) but defines **no** testing-framework code, APIs, or schemas beyond those integration points.

**Scope:** analysis only. No code in either migrated repository, in the testing-framework repository, or in AI-Hub-New has been modified.

---

# 2. Repository Findings

## 2.1 ATS Resume Assistant

### 2.1.1 Project Structure

```
ATS-Resume-Assistant/
├── streamlit_app.py        # Main UI entry point (active)
├── app.py                  # Legacy CLI entry point (superseded)
├── ats_engine.py           # Advanced engine (imports Streamlit; partially orphaned)
├── auth.py                 # Streamlit-authenticator wrapper
├── file_utils.py           # PDF/DOCX/TXT text extraction
├── generate_documents.py   # DOCX generation with styling
├── system_prompts.py       # 4 curated prompt templates (apparently unused by entry point)
├── history_manager.py      # JSON-file generation history (unreferenced by entry point)
├── feedback_manager.py     # JSON-file feedback (unreferenced by entry point)
├── usage_tracker.py        # JSON-file daily usage limits (unreferenced by entry point)
├── create_user.py          # One-off hash generator (contains plaintext passwords)
├── generate_password.py    # One-off hash generator
├── users.yaml              # COMMITTED user database with bcrypt hashes
├── auth_config.yaml        # COMMITTED cookie signing key (plaintext)
├── requirements.txt
├── runtime.txt             # python-3.11 (Streamlit Cloud indicator)
├── templates/              # docxtpl templates (currently unused)
├── outputs/                # Generated DOCX files (committed)
├── analysis/               # Generated analysis text (committed)
└── screenshots/
```

### 2.1.2 Streamlit / UI-Specific Code

| File | Details |
|------|---------|
| `streamlit_app.py` | Entire file. `st.file_uploader`, `st.text_area`, `st.button`, `st.session_state`, `st.spinner`, `st.download_button`, `st.metric`, `st.progress`, `st.columns`, `st.expander`. |
| `ats_engine.py` | `import streamlit as st` at module level; reads `st.secrets["OPENAI_API_KEY"]`. |
| `auth.py` | `streamlit_authenticator` (`stauth.Authenticate`), `st.tabs`, `st.text_input`, renders signup form directly in Python. |

### 2.1.3 Core Business Logic

- **Keyword-based ATS scoring** (`ats_engine.py`): `STOPWORDS`, `TECH_KEYWORDS` sets; `extract_keywords()`, `calculate_keyword_match()` (matched/missing keyword lists, capped score bands 88/72/48), `generate_ats_analysis()`.
- **Text cleanup** (`ats_engine.py`): `clean_generated_text()` — markdown stripping, bullet encoding fix, "AI garbage" section removal, enterprise word normalization (`realworld`→`real-world` etc.), regex fixes.
- **Pipeline** (`ats_engine.py`): `run_resume_pipeline()` chaining keyword match → tailored resume → cover letter.
- **DOCX generation** (`generate_documents.py`): section-based formatting (name heading, contact line, section headings, bullets) using `python-docx`.
- **File handling** (`file_utils.py`): PDF (pypdf), DOCX (python-docx), TXT extraction; `validate_file_size()` (5 MB) — **exists but is never called** by the entry point.

### 2.1.4 AI / LLM Logic

- Direct `openai.OpenAI` client (`streamlit_app.py`, `app.py`, `ats_engine.py`), models `gpt-4.1-mini` and `gpt-4.1`, temperatures 0.4–0.7.
- **Two divergent implementations coexist:**
  1. `streamlit_app.py` — single LLM call returning 6 sections delimited by `===ATS_SCORE===`, `===MATCHING_KEYWORDS===`, `===MISSING_KEYWORDS===`, `===IMPROVEMENT_SUGGESTIONS===`, `===TAILORED_RESUME===`, `===COVER_LETTER===`; parsed with string splitting.
  2. `ats_engine.py` — multi-call pipeline (keyword match → tailored resume → cover letter → interview questions) with separate prompts per step.
- `generate_interview_questions()` is **defined twice** in `ats_engine.py` (lines ~515 and ~682); the second definition shadows the first.
- `clean_ats_score()` is duplicated in `streamlit_app.py` and `ats_engine.py`.

### 2.1.5 LangGraph Workflows

**None.** ATS Resume Assistant does not use LangGraph. The target architecture document (04_System_Architecture.md) anticipates LangGraph for AI orchestration, so the ATS pipeline is a candidate to become a LangGraph workflow — but no existing graph needs porting.

### 2.1.6 Prompt Handling

- `streamlit_app.py`: one large `SYSTEM_PROMPT` inline + user prompt built by f-string interpolation.
- `ats_engine.py`: prompts inline per function (resume, cover letter, interview questions), f-string interpolation.
- `app.py` (CLI): its own smaller `SYSTEM_PROMPT`.
- `system_prompts.py`: four well-developed prompts (`ATS_ANALYSIS_PROMPT`, `ACHIEVEMENT_REWRITE_PROMPT`, `RESUME_GENERATION_PROMPT`, `COVER_LETTER_PROMPT`) — **not imported by any active entry point**; they belong to a fuller pipeline that is not wired up in the committed code.

### 2.1.7 Data Models

- No formal models. Plain dicts for pipeline results; no Pydantic/dataclasses.
- `users.yaml` acts as the user "database" (credentials: usernames → email/name/password-hash/role/daily_limit).
- `history_manager`, `feedback_manager`, `usage_tracker` write one JSON file per event to `data/history/`, `data/feedback/`, `data/usage/`.

### 2.1.8 File / Document Processing

- Extraction: `file_utils.py` (pypdf, python-docx, raw txt).
- Generation: `generate_documents.py` builds DOCX via `python-docx` with hardcoded styling heuristics. **Problem:** contact-line detection hardcodes personal values (`"Berlin"`, `"Germany"`).
- `templates/` contains `resume_template.docx` and `cover_letter_template.docx` (docxtpl) — **unused** by the active code path; `generate_documents.py` builds documents from scratch instead.

### 2.1.9 Authentication

- `streamlit-authenticator` cookie-based login + signup (`auth.py`).
- Credentials in `users.yaml` (bcrypt hashes), config in `auth_config.yaml` with `preauthorized.emails`.
- Registration writes new users into `users.yaml` from the web process (file-write concurrency hazard).

### 2.1.10 Session / State Management

- `st.session_state` keys: `generated`, `ats_score`, `matching_keywords`, `missing_keywords`, `improvement_suggestions`, `tailored_resume`, `cover_letter`, `resume_path`, `cover_letter_path`, `timestamp`.
- No persistence beyond the Streamlit runtime. Refresh loses results; files survive on disk only.

### 2.1.11 External Dependencies

`requirements.txt` (pinned): `streamlit 1.35.0`, `openai 1.16.2`, `python-dotenv 1.0.1`, `python-docx 1.1.0`, `docxtpl 0.16.8`, `pypdf 4.2.0`, `streamlit-authenticator 0.3.2`, `bcrypt 4.1.2`, `PyJWT 2.8.0`, `PyYAML 6.0.1`, `cryptography 42.0.5`, `httpx 0.27.0`. Runtime: Python 3.11 (`runtime.txt`).

### 2.1.12 Environment Variables / Secrets

- `OPENAI_API_KEY` loaded from `.env` (`load_dotenv()` in `streamlit_app.py`, `app.py`) **or** `st.secrets` (`ats_engine.py`) — inconsistent.
- Cookie signing key `some_signature_key` committed in plaintext (`users.yaml`, `auth_config.yaml`).

### 2.1.13 Database / Storage Usage

- **No database.** Filesystem only: `outputs/` (generated DOCX), `analysis/` (generated txt), `data/history|feedback|usage/` (JSON), `users.yaml` (credentials).
- Generated files and analysis outputs are committed to the repository.
- History JSON stores a 300-char preview of the job description (user content stored unencrypted on disk).

### 2.1.14 Reusable Modules

- `file_utils.py` — clean, UI-agnostic. KEEP (minor refactor for bytes vs file objects).
- `generate_documents.py` — reusable with refactor (remove hardcoded location heuristics).
- `system_prompts.py` — high-quality prompt assets. KEEP as prompt templates.
- `ats_engine.py` keyword logic — KEEP after decoupling from Streamlit.
- `history_manager.py` / `feedback_manager.py` / `usage_tracker.py` — logic shape is reusable; storage backend must be replaced with PostgreSQL.

### 2.1.15 Code That Should NOT Be Carried Into AI Hub

- `app.py` (legacy CLI — superseded by `streamlit_app.py`).
- `create_user.py`, `generate_password.py` (one-off scripts; also leak plaintext passwords).
- `users.yaml`, `auth_config.yaml` (secrets in git; superseded by Supabase Auth).
- `outputs/`, `analysis/`, `screenshots/`, `templates/.docx` (empty file), `__pycache__/`, `.DS_Store`.
- The duplicate `generate_interview_questions()` definition and duplicated `clean_ats_score()`.
- The unused second prompt/pipeline implementation (see 2.1.4 — decision needed in 5.1).

### 2.1.16 Potential Security Concerns

1. **Committed credentials:** `users.yaml` (bcrypt hashes of weak shared passwords) and `create_user.py` (plaintext `Admin123` / `Test123`) are in git history. Any migration must rotate these and scrub the secrets before reuse.
2. **Hardcoded cookie signing key** `some_signature_key`.
3. **`preauthorized.emails`** grants signup to a fixed email list; the signup flow itself has no verification.
4. **Prompt injection:** resume text and job description are interpolated raw into prompts with no delimiters/instructions to treat them as data.
5. **File upload validation gaps:** extension check only; size validator exists but is not invoked; no MIME/content validation.
6. **No rate limiting** on AI calls (usage_tracker exists but is not wired into the active entry point).
7. **User data on shared filesystem** keyed by username, no access control at file level.
8. **Secret handling inconsistent** (`os.getenv` vs `st.secrets`).

### 2.1.17 Architectural Problems When Moving to Next.js + FastAPI

1. **Session state must move server-side.** `st.session_state` is Streamlit-runtime-bound; FastAPI is stateless → persist results/conversations in PostgreSQL and reference by ID.
2. **Downloads must move to storage.** `st.download_button` reads local files → replace with Supabase Storage + signed URLs / streaming responses.
3. **Synchronous LLM calls block the UI.** Streamlit spinner hides latency; in FastAPI, ATS generation (multiple LLM calls, DOCX rendering) should be a background task with a job/polling or SSE model.
4. **`ats_engine.py` is coupled to Streamlit** via `st.secrets` — must inject config/client instead.
5. **Marker-based LLM parsing (`===…===`)** is fragile (no retries, no schema validation). Target: JSON structured outputs or LangGraph structured state.
6. **Two competing implementations** (single-call vs multi-call pipeline) must be reconciled before porting; do not port both.
7. **Hardcoded personal data** in DOCX heuristics ("Berlin"/"Germany") breaks for any other user.
8. **File-system state** (`outputs/`, `data/`) breaks horizontal scaling and multi-user isolation → replace with DB + object storage.
9. **No user IDs in history/feedback/usage** beyond username strings → replace with FK to `users` table.

---

## 2.2 AI IT Support Copilot

### 2.2.1 Project Structure

```
AI-IT-Support-Copilot/
├── streamlit_app.py       # Main UI entry point (active)
├── app.py                 # CLI harness (bypasses streamlit)
├── workflow.py            # LangGraph StateGraph definition
├── state.py               # ITSupportState TypedDict
├── ticketing.py           # Ticket generation + keyword status machine
├── llm.py                 # Shared ChatOpenAI instance
├── nodes/
│   ├── classify_issue.py
│   ├── retrieve_knowledge.py
│   ├── ask_questions.py
│   ├── troubleshoot.py
│   ├── escalate.py
│   └── root_cause.py      # NOT part of the graph; called manually
├── utils/
│   └── knowledge_loader.py
├── knowledge_base/        # 7 static .txt guides
├── test_openai.py
└── screenshots/
```

### 2.2.2 Streamlit / UI-Specific Code

- `streamlit_app.py` (entire file): `st.chat_input`, `st.chat_message`, `st.session_state` (`messages`, `current_ticket`, `issue_type`), sidebar with "Start New Ticket" reset via `st.rerun()`.
- Significant **orchestration logic lives in the UI layer**: full graph only on first message; follow-ups call the `troubleshoot` node directly; ticket lifecycle updates happen in the UI; root-cause generation is triggered from the UI when the ticket resolves. This logic must be extracted into a service layer.

### 2.2.3 Core Business Logic

- `ticketing.py`: ticket dict `{ticket_id, priority, assigned_team, status}`; status machine via keyword lists (`Open → In Progress → Awaiting Confirmation → Resolved`, `Escalated`).
- `utils/knowledge_loader.py`: issue-type → knowledge file mapping with fallback to `general_support.txt`.
- `nodes/ask_questions.py`: hardcoded follow-up questions per issue type.

### 2.2.4 AI / LLM Logic

- Shared `ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=60, max_retries=2)` via `llm.py`.
- Three LLM-backed nodes: classify (categorical), troubleshoot (KB + conversation), root cause (structured summary).
- No system prompt separation; all prompts are inline f-strings.

### 2.2.5 LangGraph Workflows

`workflow.py`: `StateGraph(ITSupportState)` with nodes `classify_issue → (security_issue ? escalate : retrieve_knowledge) → ask_questions → troubleshoot → END`.

Observations:
- The graph is only invoked for the **first** user message; subsequent turns bypass it and call `troubleshoot()` directly (`streamlit_app.py`).
- `nodes/root_cause.py` is **not registered in the graph**; it is called manually after resolution.
- No checkpointer / thread support — state is reconstructed per message.
- `classify_issue` returns the raw LLM string with **no validation** against the allowed categories; an unexpected string silently breaks routing and knowledge lookup.
- Category mismatch (see 2.2.13): classifier categories ≠ knowledge loader categories.

### 2.2.6 Prompt Handling

- All prompts inline in node files (f-strings). No prompt registry, no versioning, no system/user separation.

### 2.2.7 Data Models

- `ITSupportState` (TypedDict): `user_issue`, `conversation_history`, `issue_type`, `knowledge_base`, `follow_up_question`, `troubleshooting_steps`, `resolution`, `root_cause_summary`, `escalation_needed`.
- Ticket: plain dict. **No persistence** — "persistent ticket IDs" in the README means per-browser-session only.

### 2.2.8 File / Document Processing

- Only static knowledge-base `.txt` loading. No uploads, no document generation.

### 2.2.9 Authentication

- **None.** No login, no user identity, no rate limiting.

### 2.2.10 Session / State Management

- `st.session_state.messages` (chat history), `current_ticket`, `issue_type`. All in-memory; lost on refresh/server restart. Tickets are not stored anywhere.

### 2.2.11 External Dependencies

`requirements.txt` (unpinned): `langgraph`, `langchain`, `langchain-openai`, `openai`, `python-dotenv`.

### 2.2.12 Environment Variables / Secrets

- `OPENAI_API_KEY` via `python-dotenv` only. No other secrets.

### 2.2.13 Database / Storage Usage

- **None.** Knowledge base = static text files. Ticket IDs = `random.randint(1000, 9999)` — no uniqueness guarantee, collision-prone, not sequential.

### 2.2.14 Reusable Modules

- `nodes/*` — small, testable, state-in/state-out functions. KEEP as LangGraph nodes.
- `workflow.py` — KEEP, extended with a checkpointer and proper turn-based invocation.
- `state.py` — KEEP as the LangGraph state model (move to Pydantic for validation).
- `ticketing.py` — REFACTOR into a DB-backed service (status machine logic preserved).
- `utils/knowledge_loader.py` — KEEP; likely superseded later by vector/RAG retrieval (README's stated direction).
- `knowledge_base/*.txt` — KEEP as seed content; migrate to DB or keep as assets.

### 2.2.15 Code That Should NOT Be Carried Into AI Hub

- `app.py` (CLI harness; also incomplete — its `initial_state` omits keys the `troubleshoot` node reads).
- `test_openai.py` (dev scratch).
- `screenshots/`, `.DS_Store`.
- `print()` debugging scattered through nodes (replace with structured logging).

### 2.2.16 Potential Security Concerns

1. **No authentication or authorization at all** — anyone can consume OpenAI credits.
2. **Prompt injection:** raw user messages and accumulated conversation history are interpolated into every LLM call with no data/meta delimiters.
3. **No rate limiting** or usage quotas.
4. **Unbounded prompt growth:** full conversation history is re-sent on every turn; costs and context window grow linearly.
5. **Knowledge base content includes internal-looking details** (e.g., "Corporate VPN Gateway VPN-BERLIN-01") — treat as placeholder, review before production.
6. Ticket data (if it gains persistence) would contain user-reported issues — needs access control like any other user data.

### 2.2.17 Architectural Problems When Moving to Next.js + FastAPI

1. **Chat state must be server-side:** replace `st.session_state` with DB-backed conversations; LangGraph should use a checkpointer keyed by thread ID.
2. **Orchestration must leave the UI:** the current split (graph once, then direct node calls, ticket logic, root-cause trigger all in `streamlit_app.py`) must become an API/service with explicit endpoints (send message, get ticket, resolve, etc.).
3. **Long-running LLM calls** need background processing or streaming (SSE/WebSocket) for the Next.js chat UI.
4. **Ticket persistence:** in-memory tickets → PostgreSQL `tickets` table; deterministic unique IDs (sequence/UUID), not `random.randint`.
5. **Conversation history unbounded** → implement summarization/trimming or store messages and let the LLM layer select a window.
6. **Category validation:** wrap classification with a fixed allowed-set check (or structured output), since routing and KB selection depend on it.
7. **Category mapping gaps:** classifier outputs (`network_issue`, `hardware_issue`, `access_issue`) fall back to the general KB; `email_issue`, `printer_issue`, `m365_issue`, `active_directory_issue` exist in the KB mapping but are not classifier categories. Decide the canonical category list (INVESTIGATE).
8. **Escalation node appends to `resolution`** which may be empty on the direct-escalation path (first message, security issue) — behavior should be made explicit when re-implementing.
9. **No auth/user concept** — needs Supabase Auth + per-user conversations/tickets.

---

# 3. Migration Map

## 3.1 Architecture Direction

```text
CURRENT (both apps)
─────────────────────────────────────────────
Streamlit UI (streamlit_app.py)
        ↓  st.session_state
Python application logic (pipeline / nodes / ticketing)
        ↓  direct calls
AI services (OpenAI chat completions, LangGraph graph)
        ↓
Filesystem (outputs/, data/, users.yaml, knowledge_base/)

TARGET (AI Hub — multi-application platform)
─────────────────────────────────────────────
Next.js frontend (one shell, per-app routes)
        ↓  HTTPS / REST (JWT Bearer)
FastAPI backend (modular monolith, domain registry)
        ↓  domain contract — add an app without restructuring the platform
AI Application Domains (pluggable, one package each)
  ├─ Resume ATS        (migrated now)
  ├─ Support Copilot   (migrated now)
  ├─ Career Coach      (future)
  ├─ Interview Coach   (future)
  ├─ Job Matching      (future)
  └─ …                 (other AI assistants)
        ↓  shared ai_core (LLM client factory, prompt registry,
        │                 LangGraph workflow runner + checkpointer, run records)
PostgreSQL (Supabase)  +  Supabase Storage

Reserved future layer (NOT implemented now, no assumptions about its code):
  AI Testing / Evaluation Framework — consumes shared ai_core run records
  and domain contracts to evaluate any AI application or agent.
```

## 3.2 Module Classification

### ATS Resume Assistant

| Existing module | Classification | Notes |
|-----------------|----------------|-------|
| `streamlit_app.py` (UI) | **REMOVE** | Replaced by Next.js pages. Its 6-section single-call prompt/parse logic is the baseline to port into a service (REPLACE parsing with structured output). |
| `app.py` (CLI) | **REMOVE** | Superseded. |
| `ats_engine.py` keyword logic (`STOPWORDS`, `TECH_KEYWORDS`, `extract_keywords`, `calculate_keyword_match`) | **KEEP** | Port as-is into a domain service; drop the `import streamlit` (inject OpenAI client/config). |
| `ats_engine.py` LLM generators + pipeline | **REFACTOR** | Reconcile with the single-call approach (INVESTIGATE which is authoritative); dedupe `generate_interview_questions`; extract to LangGraph workflow per target architecture. |
| `file_utils.py` | **KEEP** | Minor refactor to accept bytes/file-like objects for FastAPI `UploadFile`. |
| `generate_documents.py` | **REFACTOR** | Keep DOCX styling; remove hardcoded "Berlin"/"Germany" contact heuristics; return bytes for storage streaming. |
| `system_prompts.py` | **KEEP** | Store as prompt templates/registry in the AI service layer. |
| `auth.py` | **REPLACE** | Supabase Auth (per 04_System_Architecture.md / 07_API_Design.md). |
| `history_manager.py` | **REPLACE** | Logic shape → `generation_history` DB table + service. |
| `feedback_manager.py` | **REPLACE** | Logic shape → `feedback` DB table + service. |
| `usage_tracker.py` | **REPLACE** | Daily limits → DB-backed quota checks (aligned with API rate limiting in 07_API_Design.md). |
| `create_user.py`, `generate_password.py` | **REMOVE** | One-off scripts; plaintext passwords. |
| `users.yaml`, `auth_config.yaml` | **REMOVE** | Secrets/credentials in git; Supabase Auth replaces them. Rotate any reused passwords. |
| `templates/*.docx` (docxtpl) | **INVESTIGATE** | Currently unused; decide whether docxtpl templates or programmatic `python-docx` is the long-term DOCX strategy. |
| `outputs/`, `analysis/` artifacts | **REMOVE** | Generated artifacts; replace with Supabase Storage objects. |
| `requirements.txt` | **REFACTOR** | FastAPI replaces Streamlit; pin versions in `backend/`. |

### AI IT Support Copilot

| Existing module | Classification | Notes |
|-----------------|----------------|-------|
| `streamlit_app.py` (UI) | **REMOVE** | Replaced by Next.js chat UI. Its orchestration logic (turn handling, ticket lifecycle, root-cause trigger) moves into the FastAPI service layer. |
| `app.py` (CLI) | **REMOVE** | Superseded. |
| `workflow.py` | **KEEP** | Port as the LangGraph workflow; add checkpointer (thread_id), structured state, and category validation. |
| `state.py` | **REFACTOR** | Keep shape; consider Pydantic model with validation. |
| `nodes/classify_issue.py` | **REFACTOR** | Keep prompt; add allowed-category validation / structured output; remove `print()`. |
| `nodes/retrieve_knowledge.py` | **KEEP** | Port unchanged; later extend toward vector retrieval (README roadmap). |
| `nodes/ask_questions.py` | **KEEP** | Port as-is; possibly expand later. |
| `nodes/troubleshoot.py` | **REFACTOR** | Keep prompt; move history management to message store; remove `print()`. |
| `nodes/escalate.py` | **REFACTOR** | Keep logic; fix `resolution +=` assumption; persist escalation on the ticket. |
| `nodes/root_cause.py` | **KEEP** | Port as node/service; consider adding it to the graph lifecycle explicitly. |
| `ticketing.py` | **REPLACE** | Status machine logic preserved; storage → PostgreSQL `tickets` table; unique deterministic IDs. |
| `utils/knowledge_loader.py` | **KEEP** | Port; canonicalize category mapping (INVESTIGATE). |
| `knowledge_base/*.txt` | **KEEP** | Seed content for KB storage/retrieval service. |
| `llm.py` | **KEEP** | Becomes the shared AI service LLM client factory in AI Hub. |
| `test_openai.py` | **REMOVE** | Dev scratch. |
| `requirements.txt` | **REFACTOR** | Pin versions; move to `backend/` alongside FastAPI deps. |

---

## 3.3 Platform Extensibility Requirements (Domain Contract)

To guarantee that adding future applications (Career Coach, Interview Coach, Job Matching, others) never requires restructuring the platform, the backend adopts a **pluggable domain contract**. Each AI application domain is one Python package that exposes:

1. **Pydantic schemas** — request/response models for its API.
2. **APIRouter(s)** — mounted by the core app factory; registration = import, no core changes.
3. **Service layer** — the ported business logic (e.g., ATS keyword engine, ticket status machine).
4. **Optional LangGraph workflow(s)** — pure state→state graphs registered with the shared workflow runner.
5. **Prompt assets** — versioned prompts in the shared prompt registry.
6. **DB models/migrations** — owned by the domain, applied through the shared Alembic baseline.

The shared **`ai_core`** layer (used by every domain, never by the frontend) provides:

- LLM client factory (provider/model-agnostic; per-domain model/temperature config).
- Prompt registry (versioned prompt IDs).
- LangGraph workflow runner with a PostgreSQL checkpointer (thread/conversation IDs).
- **Run records**: every AI interaction persisted in structured form (user, domain, workflow, prompt ID/version, model, input/output, state, latency). This is the substrate that both product features (history) and the future evaluation layer will consume.
- No domain may bypass `ai_core` to call model providers directly.

**What changes when a new app is added:** one new domain package + its frontend routes. The core, auth, storage, and quota services are untouched.

## 3.4 Reserved Integration Points — AI Testing / Evaluation Framework

Status: **future architectural dependency only.** The repository (AI-Testing-Framework) is unfinished, is not migrated, is not integrated, and no assumption is made about its implementation. Nothing below implements it; these are accommodations in the *current* design so that it can plug in later without rework:

1. **Structured run records** (see `ai_core` above) — persisted from day one, so historical data exists whenever the evaluation layer arrives.
2. **Deterministic workflow invocation** — LangGraph graphs remain pure functions of state; invokable headlessly (no UI, no Streamlit artifacts), with stable, typed state schemas.
3. **Model/provider abstraction** — the LLM client factory isolates provider specifics so an evaluation layer can swap models or inject mock/recorded responses.
4. **Versioned prompts** — evaluation can reference exact prompt versions used in a run.
5. **Domain discoverability** — the domain registry lets a future evaluation layer enumerate registered applications/agents and their workflows instead of hardcoding them.
6. **Separation** — evaluation datasets, rubrics, and results will live in their own namespace/schema, introduced only when the framework is actually integrated.

Explicitly **not** done now: no testing package, no evaluation APIs, no datasets, no rubric schemas, no import of the framework repository.

---

# 4. Recommended Repository Organization (AI-Hub-New)

Monorepo, modular monolith backend, consistent with 04_System_Architecture.md:

```text
AI-Hub-New/
├── docs/                          # Existing planning docs + this analysis
├── frontend/                      # Next.js (TypeScript, Tailwind) — one shell, per-app routes
│   └── app/
│       ├── (auth)/                # login/register (Supabase Auth)
│       ├── dashboard/             # unified home across all apps
│       └── apps/
│           ├── resume-ats/        # ATS Resume Assistant UI (migrated)
│           ├── support/           # IT Support Copilot chat UI (migrated)
│           ├── career-coach/      # future
│           ├── interview-coach/   # future
│           └── job-matching/      # future
├── backend/                       # FastAPI modular monolith
│   ├── app/
│   │   ├── main.py                # app factory: auto-mounts domains + middleware
│   │   ├── core/                  # config, secrets, security, logging, domain registry
│   │   ├── api/v1/                # thin routers: auth, users + per-domain mounts
│   │   ├── domains/               # ★ pluggable AI application domains (one package each)
│   │   │   ├── resume_ats/        # ATS Resume Assistant — routers, services, workflow, prompts
│   │   │   ├── support_copilot/   # IT Support Copilot — routers, services, workflow, kb, ticketing
│   │   │   ├── career_coach/      # future
│   │   │   ├── interview_coach/   # future
│   │   │   ├── job_matching/      # future
│   │   │   └── …                  # other AI assistants
│   │   ├── ai_core/               # shared by all domains: LLM client factory, prompt registry,
│   │   │                          #   LangGraph runner + checkpointer, run records
│   │   ├── services/              # shared: storage (Supabase), documents (DOCX),
│   │   │                          #   quotas, notifications
│   │   ├── models/                # SQLAlchemy/Pydantic models
│   │   └── db/                    # engine, sessions, migrations (Alembic)
│   ├── assets/
│   │   ├── prompts/               # per-domain prompt assets (versioned)
│   │   └── knowledge_base/        # support copilot .txt guides (or seeded DB)
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── infra/                         # Terraform, Docker, CI/CD (per roadmap)
└── README.md

Reserved (future, NOT implemented now — see §3.4):
  evaluation/                      # AI Testing / Evaluation Framework integration
                                   # point; will consume ai_core run records and
                                   # the domain registry. No code, schema, or
                                   # API for it is defined at this stage.
```

Notes:
- The ATS app's career functions map onto the `resumes`, `cover-letters`, `interviews` domains in 07_API_Design.md, but are owned by the `resume_ats` domain package.
- The IT Support Copilot is a **new domain** not present in the AI Hub docs: add a `support` domain (endpoints such as `POST /api/v1/support/sessions`, `POST /api/v1/support/sessions/{id}/messages`, `GET /api/v1/support/tickets`). Update 04/05/07 docs accordingly.
- Future apps (Career Coach, Interview Coach, Job Matching) each become one `domains/` package plus frontend routes; no core changes (see §3.3).
- LangGraph checkpoints live in Postgres (`langgraph-checkpoint-postgres`), which aligns with the Supabase PostgreSQL choice and keeps run records in one place.

---

# 5. Implementation Sequence

Preserving working functionality is the priority: the Streamlit apps remain untouched and runnable while AI Hub is built beside them (strangler approach). Parity checks compare FastAPI output against the Streamlit apps before frontend wiring.

**Phase 0 — Decisions & Setup**
1. Resolve open INVESTIGATE items: authoritative ATS pipeline variant; canonical IT support categories; docxtpl vs python-docx; ticket ID scheme; KB storage (files vs DB). *(Resolved/closed September 2026 — see §8 Decision Log.)*
2. Define the **domain contract** (§3.3) and `ai_core` interfaces (LLM client factory, prompt registry, workflow runner, run-record schema) — validated against the two migrated apps, not invented in the abstract.
3. Scaffold monorepo: `frontend/` (Next.js + TS + Tailwind), `backend/` (FastAPI with domain registry + auto-mount), CI skeleton, env management, Supabase project, Alembic baseline.
4. Rotate credentials exposed in the old repos; never copy `users.yaml`/`auth_config.yaml`/`create_user.py` into AI Hub.
5. Explicitly exclude the AI Testing Framework from this phase and from all MVP phases (reserved per §3.4).

**Phase 1 — Backend Foundation & Shared AI Core**
6. `core/` config + secrets, Supabase Auth JWT validation middleware, logging, domain registry.
7. Build `ai_core`: LLM client factory (port of `llm.py`), versioned prompt registry, LangGraph runner with PostgreSQL checkpointer, **run-record persistence** (enabled from day one so future evaluation has history).
8. DB schema: users, plus shared tables (run records, conversations, generation_history, feedback, usage) and the first domain tables (resumes, analyses, cover_letters, tickets) as migrations.

**Phase 2 — Domain 1: Resume ATS (reference domain; port first — most reuse)**
9. Port `file_utils` + `generate_documents` (bytes-based, heuristics cleaned) → shared `services/documents`.
10. Port keyword engine + chosen pipeline into `domains/resume_ats` and a LangGraph `ats_pipeline` workflow registered with `ai_core`; port `system_prompts.py` into versioned prompt assets; replace `===marker===` parsing with structured output.
11. Implement resume endpoints: `POST /resumes`, `POST /resumes/{id}/ats-analysis`, `POST /resumes/{id}/optimize`; background-task execution + job status; DOCX via Supabase Storage; every invocation writes run records through `ai_core`.
12. Port history/feedback/usage managers to DB-backed services with per-user quota enforcement.
13. Retrospective: validate the domain contract against this first real domain; adjust `ai_core` before the second domain lands.

**Phase 3 — Domain 2: Support Copilot**
14. Port LangGraph workflow with checkpointer + validated classification; move orchestration out of UI into `domains/support_copilot` session service.
15. Port `ticketing` to DB-backed service (unique IDs, status machine preserved); root cause as an explicit step; conversation store with history windowing.
16. Implement support endpoints: session create, message send (streaming-ready), ticket list/detail, resolve.
17. Load knowledge base (files or seeded DB) via `services` retrieval module.

**Phase 4 — Frontend (one shell, per-app routes)**
18. Next.js auth + layout + dashboard (Supabase Auth).
19. `apps/resume-ats`: upload resume → run analysis → results (score, keywords, suggestions) → preview/download DOCX.
20. `apps/support`: chat UI consuming session/message endpoints; ticket sidebar.
21. Wire remaining dashboard/history pages against the ported history/feedback services.

**Phase 5 — Parity, Hardening, Deprecation**
22. Side-by-side parity tests: same resume+JD and same support conversation against old Streamlit apps vs new API; fix deviations.
23. Rate limiting (07_API_Design.md limits), input validation, prompt-injection hardening, secrets audit.
24. CI/CD + deployment (per 08_Implementation_Roadmap.md), then archive the two legacy repositories as read-only references.

**Future (post-MVP, not scheduled now)**
25. New domains (Career Coach, Interview Coach, Job Matching) land as additional `domains/` packages + frontend routes.
26. AI Testing / Evaluation Framework integration: consumes existing `ai_core` run records, prompt versions, and the domain registry (§3.4). No integration work begins before the framework repository is finished.

---

# 6. Out of Scope / Explicitly Not Rebuilt

- No new features invented (job boards, notifications UI, RAG embeddings, Teams/Slack integrations) — all listed as *future* in the source READMEs or roadmap.
- No rebuild of functionality that works: keyword engine, DOCX styler, LangGraph nodes, knowledge loader, prompts are ported, not rewritten.
- No changes to the two legacy repositories or the existing AI Hub docs 01–08.
- **AI Testing Framework: not migrated, not integrated, not implemented.** No assumption is made about its current code. Only the integration points in §3.4 are reserved; no evaluation code, API, or schema is introduced at this stage.
- No platform-wide coupling to the two migrated apps: they are the first domain packages, not the shape of the platform.

# 7. Open Questions (INVESTIGATE)

1. Which ATS implementation is authoritative — `streamlit_app.py` single-call or `ats_engine.py` multi-call pipeline? They produce different outputs. *(RESOLVED — §8.1)*
2. Are `auth.py`, `history_manager.py`, `feedback_manager.py`, `usage_tracker.py` part of an uncommitted "full" ATS app variant that should also be preserved?
3. Canonical IT support category list (classifier vs knowledge loader mismatch). *(PARKED — Support Copilot out of MVP; revisit when the support domain enters scope.)*
4. DOCX strategy: programmatic `python-docx` vs `docxtpl` templates (templates exist but unused). *(RESOLVED — §8.3)*
5. Whether the IT Support Copilot belongs in the AI Hub MVP at all (docs 01–08 do not mention it) — recommended yes, as a `support` domain. *(RESOLVED — §8.2)*
6. Whether the knowledge base should migrate to DB rows or stay as versioned text assets. *(PARKED — §8.4)*
7. Minimal domain-contract granularity (schemas, router mount convention, workflow registration) — to be settled in Phase 0 against the two real domains.
8. Run-record schema boundaries — which fields are product history vs evaluation substrate; to be designed in Phase 1 and revisited when the evaluation framework integration begins (not before).

# 8. Phase 0 Decision Log

Recorded September 2026. The following Phase 0 INVESTIGATE items (§7) were
resolved by the project owner. Terminology is preserved from §7.

## 8.1 ATS Pipeline (Q1) — RESOLVED

- The ATS pipeline is a **LangGraph multi-step workflow**:
  analysis → tailored resume → cover letter.
- The deterministic keyword engine (`STOPWORDS`, `TECH_KEYWORDS`,
  `extract_keywords`, `calculate_keyword_match`) remains part of the ATS
  logic (consistent with the KEEP classification in §3.2).
- The **six-section analysis output** (ATS score, matching keywords,
  missing keywords, improvement suggestions, tailored resume, cover
  letter) remains the authoritative structured analysis baseline.
- The legacy `===marker===` parsing approach is **not** carried into AI
  Hub; structured output is required (consistent with §2.1.17.5).

## 8.2 IT Support Copilot (Q2) — RESOLVED: OUT OF MVP

- The IT Support Copilot is **not part of the AI Hub MVP**. The
  `support` domain, ticketing system, knowledge-base infrastructure, and
  Copilot AI workflows are not built during the MVP.
- The existing assistant catalogue entry remains informational only.
- The Copilot becomes the **first post-MVP domain** unless the product
  documents are explicitly changed later.
- Consequence: when the support domain later enters scope, docs 04/05/07
  must be updated to cover it (per the §4 note).

## 8.3 DOCX Strategy (Q3) — RESOLVED

- DOCX generation uses **python-docx** (programmatic; docxtpl set aside).
- Reusable document-generation logic from the legacy ATS application is
  ported where appropriate, per the REFACTOR classification in §3.2
  (heuristics cleaned; no Streamlit-specific code; return bytes).
- Generated document bytes follow the documented storage approach:
  **Supabase Storage** (see `06_AWS_Cloud_Architecture.md` §7.5), with
  canonical text content stored in the database
  (`05_Database_Design.md`: `RESUME_VERSIONS.optimized_content`,
  `COVER_LETTERS.content`).

## 8.4 Knowledge Base Storage (Q4) — PARKED

- Not implemented during the MVP (Support Copilot out of MVP).
- No knowledge-base file structure, database tables, vector/RAG
  infrastructure, or related APIs are created now.
- Revisit when the support domain enters scope.

## 8.5 Ticket ID Scheme (Q5) — PARKED

- Not implemented during the MVP (Support Copilot out of MVP).
- When the support domain enters scope, ticket IDs follow the existing
  UUID primary-key convention from `05_Database_Design.md` (§4.2, §9);
  deterministic DB-generated IDs only — never `random.randint`.
