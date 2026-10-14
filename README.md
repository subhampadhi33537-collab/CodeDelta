# CodeDelta

> **AI-powered website builder** — describe a website, watch a team of AI agents plan, design, code, review and ship it live.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 19 + Vite 8, TypeScript 5, Tailwind CSS 4, React Router 7 |
| Backend | Python 3.12, FastAPI 0.115, Pydantic v2, psycopg 3 |
| AI | LangGraph, LangChain, Groq / Ollama Cloud / Hugging Face |
| Database | Supabase (Postgres) |
| Storage | Google Drive API |
| Tracing | LangSmith |

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `winget install astral-sh.uv`)
- Node 20+ and npm 10+

## Setup

```bash
# 1. Clone
git clone <repo-url>
cd codelta

# 2. Copy and fill in secrets
cp .env.example .env
# edit .env — add JWT_SECRET, database URLs, API keys, etc.
```

### Backend

```bash
cd backend

# Install deps (creates backend/.venv automatically)
uv sync --extra dev

# Run dev server (auto-reload)
uv run uvicorn app.main:app --reload --port 8000

# Health check
curl http://localhost:8000/api/health

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
```

### Frontend

```bash
cd frontend

# Install deps
npm install

# Run dev server (proxies /api to localhost:8000)
npm run dev

# Lint
npm run lint

# Format
npm run format

# Production build
npm run build
```

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── config.py          # pydantic-settings
│   │   ├── main.py            # FastAPI app factory
│   │   └── routers/
│   │       └── health.py      # GET /api/health
│   ├── db/
│   │   └── migrations/        # numbered .sql files
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── router/
│   │   └── main.tsx
│   └── package.json
├── docs/                      # architecture docs, master prompt
├── scripts/                   # migrate.py, google_oauth_setup.py, etc.
├── .env.example
└── README.md
```

## Phase roadmap

| Phase | Status | Description |
|---|---|---|
| 0 | ✅ Done | Foundation — monorepo, FastAPI skeleton, Vite frontend, CI |
| 1 | 🔜 | Database migrations + psycopg pool |
| 2 | 🔜 | Authentication (JWT, argon2id) |
| 3 | 🔜 | Projects CRUD |
| 4 | 🔜 | AI model layer (ModelRouter, fallback chain) |
| 5 | 🔜 | LangGraph agent graph (Intent → Planner → Architect → Coders) |
| 6 | 🔜 | Reviewer, Tester, Debugger, Packager agents |
| 7 | 🔜 | SSE event streaming |
| 8 | 🔜 | Google Drive storage |
| 9 | 🔜 | Preview iframe + file editor |
| 10 | 🔜 | Full builder UI (Monaco, version history) |
| 11 | 🔜 | React + Vite output mode |
