# Supabase Database Setup & Configuration Guide

This document details how to configure Supabase Postgres for **CodeDelta**, wire the connection pooler, apply schema migrations, and manage Row Level Security (RLS).

---

## 1. Create a Supabase Project

1. Navigate to [Supabase Dashboard](https://supabase.com/dashboard) and sign in.
2. Click **New Project**.
3. Fill in:
   - **Name**: `codedelta` (or your preferred name)
   - **Database Password**: Choose a strong password (keep a copy for `.env`)
   - **Region**: Choose a region closest to your app (e.g., `Northeast Asia (Tokyo) - ap-northeast-1`)
4. Wait for database provisioning to complete (typically ~1-2 minutes).

---

## 2. Obtain Connection Strings

CodeDelta uses **two** database connection endpoints:

### A. Connection Pooler (Port `6543`) — Primary App Database
Go to **Project Settings** → **Database** → **Connection pooling**:
- **Mode**: `Transaction`
- **Port**: `6543`
- Host looks like: `aws-0-<region>.pooler.supabase.com`
- User format: `postgres.<project-ref>`

### B. Session / Direct Connection (Port `5432`) — LangGraph Checkpointer
LangGraph's checkpointing requires prepared statements and advisory locks, which need session mode:
- **Mode**: `Session` (or Direct)
- **Port**: `5432`

---

## 3. Configure `.env`

Copy `.env.example` to `.env` if not already present. Fill in your database credentials:

```dotenv
DATABASE_HOST=aws-0-ap-northeast-1.pooler.supabase.com
DATABASE_PORT=6543
DATABASE_NAME=postgres
DATABASE_USER=postgres.<your-project-ref>
DATABASE_PASSWORD=<your-database-password>

# Full connection URL for pooler (Transaction mode, port 6543)
# Note: If password contains special characters like '@', '#', '%', URL-encode them (%40, %23, etc.)
DATABASE_URL=postgresql://postgres.<your-project-ref>:<encoded-password>@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres

# Direct / Session connection for LangGraph checkpointer (port 5432)
CHECKPOINT_DATABASE_URL=postgresql://postgres.<your-project-ref>:<encoded-password>@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
```

> **Note on Password Encoding**:
> If your database password contains characters such as `@`, `%`, `:`, `/`, they must be percent-encoded in `DATABASE_URL` (for example `@` becomes `%40`).

---

## 4. Run Migrations

CodeDelta applies SQL migrations in numeric sequence from `backend/db/migrations/` and records applied versions in the `schema_migrations` table.

```bash
# Preview pending migrations (dry-run):
python scripts/migrate.py --dry-run

# Execute pending migrations:
python scripts/migrate.py
```

### Resetting Supabase Database Password
If you ever encounter `FATAL: password authentication failed for user "postgres"`:
1. Open Supabase Dashboard → **Project Settings** → **Database**.
2. Scroll to **Database Password** and click **Reset database password**.
3. Set a new password and immediately update `DATABASE_PASSWORD` and `DATABASE_URL` in `.env`.

---

## 5. Row Level Security (RLS) Architecture

In `backend/db/migrations/001_init.sql`, every table enables Row Level Security:
```sql
alter table users            enable row level security;
alter table projects         enable row level security;
alter table project_versions enable row level security;
alter table messages         enable row level security;
alter table agent_runs       enable row level security;
alter table agent_events     enable row level security;
alter table model_usage      enable row level security;
```

**Critical Security Rule:**
- **Zero public policies** are declared.
- Any request originating through the public Supabase REST / GraphQL API with the `anon` key is immediately denied access to all tables.
- Only the CodeDelta FastAPI backend, connecting with the Postgres connection credentials, can read and write data.
- Tenant isolation is strictly enforced at the application and query layer: all project queries, files, versions, and runs filter by `current_user.id`.
