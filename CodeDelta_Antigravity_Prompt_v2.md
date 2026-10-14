# CodeDelta: Build Prompt for Antigravity (v2)

> How to use: save this as `docs/MASTER_PROMPT.md` in the repo. In Antigravity, run ONE phase at a time:
> "Execute Phase N from docs/MASTER_PROMPT.md. Show the Implementation Plan first."
> Approve the plan, let the agent build, check the Walkthrough, then start the next phase.
> Real keys live only in `.env` (git-ignored). Never paste them into this file or into chat.

---

## 1. Mission

Build **CodeDelta**, a Lovable-style website where a registered user types what website they want and a team of AI agents plans, designs, codes, reviews, fixes and packages it. The user sees progress live, previews the result, can keep editing by chat, and every version is saved as a zip in Google Drive under a folder named with the user's database id.

## 2. Tech stack (strict)

Use ONLY the technologies below. If you think something else is needed, ask me first and explain why.

| Area | Use |
|---|---|
| Backend | Python, **FastAPI**, **Pydantic v2** (+ `pydantic-settings`) |
| Database | **Supabase** (Postgres), reached through the `DATABASE_URL` connection string |
| Frontend | **React + Vite** (TypeScript), React Router, Tailwind CSS, Monaco editor, zod |
| AI framework | **LangChain**, **LangGraph**, **LangSmith** (tracing and evals) |
| Model providers | **Groq** (`langchain-groq`), **Hugging Face** (`langchain-huggingface`), **Ollama Cloud** free models (`langchain-ollama`) |
| Web search tool | Tavily (key already in `.env`) |
| File storage | Google Drive API (zip per project version) |

Small helper libraries are fine (PyJWT, argon2-cffi, email-validator, psycopg 3 + pool, httpx, sse-starlette, google-api-python-client, google-auth-oauthlib, langgraph-checkpoint-postgres, pytest, ruff, uv). **Do not add** SQLAlchemy, Alembic, Docker, Redis, Celery or Next.js.

Database access: plain SQL through `psycopg` (async pool). Every row is read into a Pydantic model. Migrations are numbered `.sql` files in `backend/db/migrations/` applied by `scripts/migrate.py`.

## 3. Rules for every phase

1. No secrets in code. Everything comes from `.env`; commit only `.env.example` (names, no values).
2. Do not skip phases. Finish the acceptance check before moving on.
3. Each phase ends with: tests passing, a run command that works, a short README update, and a Walkthrough.
4. Read current docs before using an API (FastAPI, LangGraph, LangChain, Groq, Ollama Cloud, HF, Drive). Pin the versions you install.
5. Validate all input with Pydantic. The user always comes from the JWT, never from a client-sent id. Never return password hashes.
6. If something is unclear or blocked, stop and ask a specific question instead of guessing.
7. Small commits, typed code, linted code.

## 4. Architecture

```
React + Vite  --(HTTPS, Bearer JWT)-->  FastAPI
                                          |-- Supabase Postgres (users, projects, versions, runs, events, checkpoints)
                                          |-- LangGraph multi-agent graph --> Model Router --> Groq / Ollama Cloud / Hugging Face
                                          |        |-- traced in LangSmith
                                          |        '-- file tools + Tavily search, inside a per-run workspace folder
                                          '-- Drive service --> Google Drive: <ROOT>/<user_id>/<project_id>_v<N>.zip
```
The browser never talks to Drive or to a model provider. Only the backend does.

## 5. Multi-agent workflow

Keep the number of LLM calls low, because the models are free-tier and rate-limited. The graph itself (conditional edges, plain Python) is the orchestrator; it does not use an LLM.

| Agent | Job | Output (Pydantic) | Model type |
|---|---|---|---|
| Intent Router | Classify the message: `new_build`, `edit`, `question`, `fix_error` | `Intent` | small, fast |
| Planner | Turn the request into name, pages, features, content, tech choice (may call Tavily) | `Plan` | strong reasoning |
| Designer | Palette, fonts, spacing, layout, section list | `DesignSpec` | general |
| Architect | One task per file, in dependency order, each with full context | `TaskPlan` | strong reasoning |
| Coder workers | Write each file (several run in parallel, capped at 2 to 3) | files via tools | coding model |
| Reviewer | Check files against plan and design, list concrete problems | `ReviewReport` | strong reasoning |
| Tester (no LLM) | Validate the site: HTML parses, linked files exist, JS syntax check, optional build | `BuildReport` | none |
| Debugger | Fix only the files named in the reports | patches via tools | coding model |
| Packager (no LLM) | Zip, upload to Drive, save the version row | `PackageResult` | none |

Flow:
```
START -> intent_router
new_build: planner -> designer -> architect -> coders (parallel, LangGraph Send) -> reviewer
edit:      retriever (pick relevant files) -> architect (edit tasks) -> coders -> reviewer
reviewer -> (problems?) -> debugger -> reviewer          max 2 loops
reviewer -> tester -> (failed?) -> debugger -> tester     max 2 loops
tester -> packager -> END
question: answer node -> END
```
Rules:
- One typed `CodeDeltaState` carries: `user_id`, `project_id`, `run_id`, `prompt`, `plan`, `design_spec`, `task_plan`, `files_changed`, `review_report`, `build_report`, `loop_counters`, `status`.
- Every LLM agent returns a Pydantic structured output. If it is invalid, retry once with the validation error, then fall back to the next model in the chain.
- Hard limits per run: max loops, max tool calls, max run time, max tokens. On a limit, stop cleanly and keep the files written so far.
- Use the LangGraph Postgres checkpointer so a run can be cancelled or resumed. (Supabase's port 6543 pooler needs `prepare_threshold=0`; if that causes trouble use `CHECKPOINT_DATABASE_URL` with the direct/session connection.)
- Optional human-in-the-loop flag: pause after the Plan so the user can approve it.
- Stream an event for every node start/end, file written, review result, test result and error. Store in `agent_events`, send to the browser over SSE.
- File tools are locked to the run's workspace folder (path-traversal safe, like coder-buddy's `safe_path_for_project`): `read_file`, `write_file`, `apply_patch`, `list_files`, `search_in_files`, `delete_file`. Coders get file tools only. Planner and Designer also get `web_search` (Tavily).
- Generated sites default to **plain HTML/CSS/JS** (instant preview, no build step). A React + Vite output mode comes later (Phase 11).
- Reference: `codebasics/coder-buddy` (planner -> architect -> coder loop, structured `Plan` / `TaskPlan`, safe file tools). Keep those ideas and add routing, design, review, debug, packaging, streaming and storage.

## 6. Model layer (all free tiers)

- Config lives in `backend/app/ai/models.yaml`: provider, model id, context size, supports tools / structured output, role. Providers: `groq`, `ollama_cloud`, `huggingface`.
- Build a `ModelRouter.get(role)` that returns a LangChain chat model, with an ordered **fallback chain** per role (rate limit, timeout, bad output, provider down -> next).
- Seed a pool of up to 10 free models, **verified live** before you seed (Groq: call its models list endpoint; Ollama Cloud: check the cloud library; HF: check Inference Providers). Starting candidates to check: Groq `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `qwen/qwen3-32b`, a Kimi K2 model; Ollama Cloud `qwen3-coder`, `deepseek-v3.1`, `gpt-oss:120b`, `glm`; Hugging Face `Qwen2.5-Coder-32B-Instruct`, `Llama-3.3-70B-Instruct`. Replace anything missing or outdated and tell me what you picked.
- Suggested roles: Intent Router = small fast model; Planner / Architect / Reviewer = strongest reasoning model; Coder / Debugger = best coding model; Designer = general model.
- Free tiers have rate limits, so: per-provider rate limiter, exponential backoff that respects `Retry-After`, keep prompts small (send only relevant files), cap parallel coders.
- Users can pick a model or leave it on **Auto**. Log provider, model, tokens, latency and success in `model_usage`.
- LangSmith: set the `LANGCHAIN_*` env vars, name every node run, and tag runs with `run_id` and `project_id`. Do not send passwords or tokens to traces.

## 7. Authentication (Pydantic + JWT, kept simple)

Pydantic v2 models validate every request and response. Passwords are hashed. Login returns one JWT. No refresh tokens.

```python
class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # validators: strip name and reject blank; lower-case email;
    # password needs at least one letter and one digit

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserPublic(BaseModel):            # the only user shape ever returned
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserPublic

class TokenPayload(BaseModel):          # validates decoded JWT claims
    sub: UUID
    email: EmailStr
    iat: int
    exp: int
```
- `POST /api/auth/register` (409 on duplicate email) hashes the password (argon2id), creates the user, creates their Drive folder (best effort, retried on first save), returns `TokenResponse`.
- `POST /api/auth/login` returns the same generic 401 "Invalid email or password" for any failure.
- `GET /api/auth/me` returns `UserPublic`.
- JWT: PyJWT, HS256, `JWT_SECRET` from env, claims `sub`, `email`, `iat`, `exp`, lifetime `ACCESS_TOKEN_MINUTES`. `get_current_user` reads the Bearer header, validates claims with `TokenPayload`, loads the user, rejects inactive users.
- Every project, run, file and download query filters by `current_user.id`. Another user's resource returns 404.
- Frontend: zod schemas that mirror the Pydantic rules, token kept in localStorage, sent as a Bearer header, cleared and redirected to login on any 401.
- Supabase tables have Row Level Security on with no public policies, so the public Supabase API can never read them. The backend is the only client.

## 8. Google Drive storage

Root folder id: `1zur8UsA64ko5cBtXXLQl0aInPLmI2U8m` (env `GOOGLE_DRIVE_ROOT_FOLDER_ID`).
```
<ROOT>/<user_id>/<project_id>_v1.zip, <project_id>_v2.zip, ...     (folder name = users.id exactly)
```
- Credentials: a service account usually cannot upload into a personal My Drive folder (storage quota error). Default to **OAuth with the refresh token of the Google account that owns the folder** (`scripts/google_oauth_setup.py` prints it once for `.env`). Also support a service account only if the folder is moved into a Shared Drive. Selected by `GOOGLE_AUTH_MODE`.
- `ensure_user_folder(user_id)`: use `users.drive_folder_id` if set, else look for a folder named `user_id` under the root, else create it; save the id. Must be idempotent.
- `upload_zip`, `download_zip` (check that the file belongs to that user's folder and a `project_versions` row owned by that user), `list_versions`, `delete_version` (keep the latest 20 per project). Retry with backoff on 429/5xx.
- Never expose Drive ids or links to the browser. Downloads go through `GET /api/projects/{id}/versions/{n}/download`, which the backend authorizes and streams.
- Zips exclude `node_modules`, `.git`, `.env*`. On restore reject `..` and absolute paths (zip-slip) and cap size and file count.
- The database is the source of truth for user -> folder -> project -> version -> Drive file id. The local workspace is only a cache; if it is missing, restore the latest zip from Drive.

## 9. Database (Supabase Postgres)

`backend/db/migrations/001_init.sql`:
```sql
create extension if not exists pgcrypto;
create extension if not exists citext;

create table users (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email citext unique not null,
  password_hash text not null,
  drive_folder_id text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  name text not null,
  initial_prompt text not null,
  status text not null default 'draft',     -- draft | building | ready | failed
  current_version int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table project_versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  user_id uuid not null references users(id) on delete cascade,
  version int not null,
  drive_file_id text not null,
  size_bytes bigint, sha256 text, run_id uuid,
  created_at timestamptz not null default now(),
  unique (project_id, version)
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  role text not null,                        -- user | assistant
  content text not null,
  created_at timestamptz not null default now()
);

create table agent_runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  user_id uuid not null references users(id) on delete cascade,
  intent text, status text not null default 'queued',
  model_choice text, error text,
  started_at timestamptz, ended_at timestamptz,
  created_at timestamptz not null default now()
);

create table agent_events (
  id bigserial primary key,
  run_id uuid not null references agent_runs(id) on delete cascade,
  seq int not null, agent text, type text not null, payload jsonb,
  created_at timestamptz not null default now()
);

create table model_usage (
  id bigserial primary key,
  run_id uuid references agent_runs(id) on delete cascade,
  agent text, provider text, model_id text,
  tokens_in int, tokens_out int, latency_ms int, success boolean,
  created_at timestamptz not null default now()
);

create index on projects (user_id);
create index on project_versions (project_id);
create index on agent_events (run_id, seq);

alter table users enable row level security;
alter table projects enable row level security;
alter table project_versions enable row level security;
alter table messages enable row level security;
alter table agent_runs enable row level security;
alter table agent_events enable row level security;
alter table model_usage enable row level security;
-- no public policies: only the backend connection can read or write
```

## 10. API

- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- Projects: `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}`
- Files: `GET /api/projects/{id}/files`, `GET/PUT /api/projects/{id}/files/{path}`
- Preview: `POST /api/projects/{id}/preview-token` (short-lived signed token), `GET /api/preview/{token}/{path}` serves the workspace files for the iframe (an iframe cannot send a Bearer header)
- Runs: `POST /api/projects/{id}/runs`, `GET /api/runs/{run_id}/events` (SSE, supports `Last-Event-ID`), `POST /api/runs/{run_id}/cancel`, `POST /api/runs/{run_id}/resume`
- Versions: `GET /api/projects/{id}/versions`, `POST /api/projects/{id}/versions/{n}/restore`, `GET /api/projects/{id}/versions/{n}/download`
- Models: `GET /api/models`
- Health: `GET /api/health`

Everything except register, login, health and the signed preview route needs a valid JWT.

## 11. Frontend pages (React + Vite)

Landing, Register, Login, Dashboard (project grid), Builder workspace (chat with live agent timeline, file tree, Monaco editor, preview iframe with device toggle, version history, model picker, download zip), Account, 404. Clean modern UI, light and dark mode, responsive, keyboard accessible. API base URL from `VITE_API_URL`.

## 12. Phases and tasks (14 phases, 95 tasks)

For each phase: Implementation Plan first, then build, then check the acceptance line.

### Phase 0: Foundation (5 tasks)
1. Create the monorepo: `frontend/`, `backend/`, `docs/`, `scripts/`.
2. Backend with `uv`: FastAPI app factory, `pydantic-settings` config, `GET /api/health`, CORS for the Vite origin.
3. Frontend with Vite + React + TypeScript + Tailwind + React Router.
4. `.gitignore`, `.env.example` (names only), root README with run steps.
5. ruff + pytest for the backend, eslint + prettier for the frontend, and a simple CI workflow that runs them.
**Accept**: health endpoint returns ok, Vite dev server runs, CI is green.

### Phase 1: Supabase database (6 tasks)
1. Document how to create the Supabase project and fill `DATABASE_*` / `DATABASE_URL` in `.env` (pooler on port 6543).
2. Async `psycopg` connection pool with the right settings for the pooler (`prepare_threshold=0`, dict rows) and a FastAPI dependency.
3. Write `001_init.sql` from section 9 and `scripts/migrate.py` that applies numbered migrations and records them.
4. Pydantic row models and small repository modules: users, projects, versions, runs, events.
5. Confirm RLS is on for every table with no public policies.
6. DB tests against a test schema or rolled-back transactions.
**Accept**: migration runs on an empty Supabase database; repository tests pass.

### Phase 2: Authentication with Pydantic (8 tasks)
1. Add `email-validator`; create `RegisterRequest`, `LoginRequest`, `UserPublic`, `TokenResponse`, `TokenPayload` with the validators from section 7.
2. Password service (argon2id): hash and verify.
3. JWT service (PyJWT): create and decode, claims validated by `TokenPayload`.
4. `POST /api/auth/register` (409 on duplicate email).
5. `POST /api/auth/login` (generic 401).
6. `get_current_user` dependency and `GET /api/auth/me`.
7. Every route uses `response_model`; add basic security headers.
8. Tests: valid register, bad email, weak password, blank name, duplicate email, wrong password, expired token, tampered token, missing token, another user's resource returns 404.
**Accept**: all tests pass; invalid input gives clear 422 errors; no hash ever appears in a response or log.

### Phase 3: Google Drive storage (8 tasks)
1. Write `docs/GOOGLE_SETUP.md`: Google Cloud project, Drive API, OAuth client, consent screen.
2. `scripts/google_oauth_setup.py` to get the refresh token for `.env`.
3. `DriveClient` with OAuth mode (default) and service-account mode (Shared Drive only), with retry and backoff.
4. `ensure_user_folder` (idempotent, no duplicates, saves `drive_folder_id`).
5. Create the user folder during registration (best effort) and lazily on first save.
6. `upload_zip` returning file id, size and sha256.
7. `download_zip` with the ownership check, plus `list_versions` and `delete_version` (keep 20).
8. Tests with a mocked Drive client and one manual script that uses a real test folder and cleans up.
**Accept**: registering a user creates a folder named with their UUID under the root; a sample zip uploads and downloads; another user cannot download it.

### Phase 4: Projects, workspace and zips (7 tasks)
1. Project CRUD endpoints, always scoped to the current user.
2. Workspace manager: `workspaces/<user_id>/<project_id>/`, cleanup of old runs, restore from Drive if missing.
3. Zip builder with exclusions.
4. Safe unzip with zip-slip and size protection.
5. "Save version" service: zip, upload, insert `project_versions`, bump `current_version`.
6. Restore and download endpoints.
7. Tests, including malicious zip entries.
**Accept**: create a project, save a version, list it, restore it, and download it.

### Phase 5: Model layer (7 tasks)
1. Provider adapters for Groq, Ollama Cloud and Hugging Face behind one interface.
2. `models.yaml` and a loader with Pydantic validation.
3. Verify the live catalogs, pick the free pool of up to 10 models, document it in `docs/MODELS.md`.
4. `ModelRouter.get(role)` with fallback chains.
5. Per-provider rate limiter and backoff that honors `Retry-After`.
6. Usage logging to `model_usage` and LangSmith setup (tracing on, run names, tags, no secrets).
7. Small script that sends the same test prompt to every pool model and prints success, latency and structured-output validity.
**Accept**: with the first model disabled, a call falls back automatically and appears in LangSmith.

### Phase 6: Agent state and tools (6 tasks)
1. Pydantic models: `Intent`, `Plan`, `DesignSpec`, `Task`, `TaskPlan` (with dependencies), `ReviewReport`, `BuildReport`, `PackageResult`.
2. `CodeDeltaState` with reducers for lists and counters.
3. Safe file tools locked to the workspace.
4. Tavily `web_search` tool with result size limits.
5. Site validator (Tester logic): HTML parses, linked files exist, `node --check` for JS if Node is available, structured error list.
6. Tests for path traversal, oversized files and the validator.
**Accept**: a hand-written sample site passes the validator; traversal attempts are rejected.

### Phase 7: Multi-agent graph (9 tasks)
1. Role prompts as versioned files in `backend/app/ai/prompts/`, one per agent.
2. Intent Router.
3. Planner and Designer with structured output.
4. Architect producing a dependency-ordered `TaskPlan`.
5. Parallel Coder workers with LangGraph `Send`, capped concurrency.
6. Reviewer.
7. Tester node and Debugger with bounded loops.
8. Packager node (zip, Drive upload, version row).
9. Wire the full graph with the Postgres checkpointer, cancellation, the optional approve-plan interrupt, and the edit path with a file retriever.
**Accept**: "Build a landing page for a coffee shop" produces a site that passes review and tests and is saved as `v1` in the user's Drive folder.

### Phase 8: Runs API and streaming (6 tasks)
1. `POST /api/projects/{id}/runs` starts a background run with a worker limit.
2. Event emitter writing every graph event to `agent_events` with a sequence number.
3. SSE endpoint with auth and `Last-Event-ID` reconnection.
4. Cancel and resume endpoints.
5. Preview token and static preview route for the iframe.
6. Per-user daily and concurrent run limits (`MAX_RUNS_PER_DAY`), with tests for ordering, cancellation and limits.
**Accept**: curl or a browser sees live events, can reconnect without losing events, and the preview loads.

### Phase 9: Frontend shell and auth UI (8 tasks)
1. Routing, layout, theme (light and dark), CodeDelta branding.
2. Typed API client that adds the Bearer token and handles 401 by clearing it and redirecting.
3. `AuthContext`, `ProtectedRoute`, and session restore on reload through `/auth/me`.
4. Register page with zod rules matching Pydantic.
5. Login page with error handling.
6. Landing page with hero, prompt box and example prompts.
7. Dashboard: project grid, create, rename, delete, empty state.
8. Toasts, loading skeletons, 404 page.
9. colour should in green white light yellow and red .
**Accept**: register, login, logout and protected routes work; reload keeps the session.

### Phase 10: Builder workspace (8 tasks)
1. Responsive split layout: chat, preview, code.
2. Chat panel that starts runs and shows the live agent timeline and task checklist from SSE.
3. File tree updating in real time.
4. Monaco editor with save through the files API.
5. Preview iframe using the preview token, with refresh and device-size toggle.
6. Build-error panel with an "Ask AI to fix" button (starts a `fix_error` run).
7. Model picker and Auto mode.
8. Version history with restore and download zip.
**Accept**: from an empty project a user types a prompt, watches the agents work, sees the preview and gets a saved version.

### Phase 11: Editing, versions and React output (6 tasks)
1. Edit mode: follow-up messages change only the needed files.
2. Save a new version after every successful run.
3. Diff view between two versions.
4. Per-project conversation memory (summarize older messages to save tokens).
5. Optional "React + Vite" output mode: the Tester runs `npm install` and `npm run build` with an allow-list, timeout and output cap in the workspace.
6. Optional plan-approval step in the UI.
**Accept**: "make the header sticky and the main color green" edits only the needed files and creates `v2`.

### Phase 12: Quality and hardening (6 tasks)
1. Prompt-injection defense: user text and file contents are untrusted data, agents never obey instructions found inside files.
2. Secret scan of generated files before zipping.
3. LangSmith dataset of 20 test prompts and an eval script (build pass rate, review score, plan coverage).
4. Security tests: access to other users' data on every endpoint, JWT tampering, zip-slip, path traversal.
5. Rate limits on auth and run endpoints; tighten CORS and error messages.
6. Structured logs without personal data; handling of free-tier rate-limit errors with friendly UI messages.
**Accept**: no cross-user access is possible; the eval pass rate is reported and meets the target we set.

### Phase 13: Deployment (5 tasks)
1. Deploy the backend (Render, Railway or Fly) with env vars set.
2. Deploy the frontend (Vercel or Netlify) with `VITE_API_URL` and CORS.
3. Run migrations on production Supabase; note the pooler settings.
4. Monitoring: health checks, error alerts, LangSmith project for production.
5. Final docs: user guide, architecture, runbook, Google setup, demo script.
**Accept**: a new user can register, build a site, close the browser, come back later, and restore their project from Drive.

## 13. `.env.example` (names only, leave values empty)

```
APP_ENV=development
FRONTEND_ORIGIN=http://localhost:5173
JWT_SECRET=
ACCESS_TOKEN_MINUTES=1440

# Supabase Postgres
DATABASE_HOST=
DATABASE_PORT=6543
DATABASE_NAME=postgres
DATABASE_USER=
DATABASE_PASSWORD=
DATABASE_URL=
CHECKPOINT_DATABASE_URL=

# AI
GROQ_API_KEY=
HUGGINGFACEHUB_API_TOKEN=
OLLAMA_API_KEY=
TAVILY_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=codedelta

# Google Drive
GOOGLE_AUTH_MODE=oauth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_SERVICE_ACCOUNT_FILE=
GOOGLE_DRIVE_ROOT_FOLDER_ID=1zur8UsA64ko5cBtXXLQl0aInPLmI2U8m

# Limits
MAX_RUNS_PER_DAY=50
WORKSPACE_DIR=./workspaces
```
Frontend `.env`: `VITE_API_URL=http://localhost:8000`

## 14. Done means

- Register with name, email, password; a Drive folder named with the user id appears.
- Login returns a JWT; Pydantic validates every request; users only see their own data.
- A prompt starts the agent team, progress streams live, the preview works.
- Every successful run is saved as a versioned zip in the user's own Drive folder and can be restored or downloaded.
- Groq, Hugging Face and Ollama Cloud free models are used by role with automatic fallback, and every run is traced in LangSmith.

## 15. Start now

1. Read this whole file.
2. Write the Implementation Plan for **Phase 0 only**, with open questions at the end.
3. Wait for my approval, build Phase 0, verify it, write the Walkthrough, then stop.
