-- ============================================================
-- CodeDelta  –  001_init.sql
-- Applies to: Supabase (Postgres 15+)
-- Run via:  python scripts/migrate.py
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────────────────────
create extension if not exists pgcrypto;
create extension if not exists citext;

-- ── schema_migrations  (migration bookkeeping) ────────────────────────────────
create table if not exists schema_migrations (
  version   text primary key,
  applied_at timestamptz not null default now()
);

-- ── users ─────────────────────────────────────────────────────────────────────
create table users (
  id            uuid        primary key default gen_random_uuid(),
  name          text        not null,
  email         citext      unique not null,
  password_hash text        not null,
  drive_folder_id text,
  is_active     boolean     not null default true,
  created_at    timestamptz not null default now()
);

-- ── projects ──────────────────────────────────────────────────────────────────
create table projects (
  id              uuid        primary key default gen_random_uuid(),
  user_id         uuid        not null references users(id) on delete cascade,
  name            text        not null,
  initial_prompt  text        not null,
  status          text        not null default 'draft',
  -- status: draft | building | ready | failed
  current_version int         not null default 0,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- ── project_versions ──────────────────────────────────────────────────────────
create table project_versions (
  id            uuid        primary key default gen_random_uuid(),
  project_id    uuid        not null references projects(id) on delete cascade,
  user_id       uuid        not null references users(id) on delete cascade,
  version       int         not null,
  drive_file_id text        not null,
  size_bytes    bigint,
  sha256        text,
  run_id        uuid,
  created_at    timestamptz not null default now(),
  unique (project_id, version)
);

-- ── messages ──────────────────────────────────────────────────────────────────
create table messages (
  id          uuid        primary key default gen_random_uuid(),
  project_id  uuid        not null references projects(id) on delete cascade,
  role        text        not null,   -- user | assistant
  content     text        not null,
  created_at  timestamptz not null default now()
);

-- ── agent_runs ────────────────────────────────────────────────────────────────
create table agent_runs (
  id           uuid        primary key default gen_random_uuid(),
  project_id   uuid        not null references projects(id) on delete cascade,
  user_id      uuid        not null references users(id) on delete cascade,
  intent       text,
  status       text        not null default 'queued',
  -- status: queued | running | done | failed | cancelled
  model_choice text,
  error        text,
  started_at   timestamptz,
  ended_at     timestamptz,
  created_at   timestamptz not null default now()
);

-- ── agent_events ──────────────────────────────────────────────────────────────
create table agent_events (
  id         bigserial   primary key,
  run_id     uuid        not null references agent_runs(id) on delete cascade,
  seq        int         not null,
  agent      text,
  type       text        not null,
  payload    jsonb,
  created_at timestamptz not null default now()
);

-- ── model_usage ───────────────────────────────────────────────────────────────
create table model_usage (
  id         bigserial   primary key,
  run_id     uuid        references agent_runs(id) on delete cascade,
  agent      text,
  provider   text,
  model_id   text,
  tokens_in  int,
  tokens_out int,
  latency_ms int,
  success    boolean,
  created_at timestamptz not null default now()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
create index on projects        (user_id);
create index on project_versions(project_id);
create index on messages        (project_id);
create index on agent_runs      (project_id);
create index on agent_runs      (user_id);
create index on agent_events    (run_id, seq);
create index on model_usage     (run_id);

-- ── Row Level Security ────────────────────────────────────────────────────────
-- RLS is ON for every table.
-- NO public policies are created — only the service-role backend connection
-- can read or write (Supabase service key bypasses RLS).
alter table users            enable row level security;
alter table projects         enable row level security;
alter table project_versions enable row level security;
alter table messages         enable row level security;
alter table agent_runs       enable row level security;
alter table agent_events     enable row level security;
alter table model_usage      enable row level security;
