#!/usr/bin/env python
"""
scripts/migrate.py
──────────────────
Applies numbered SQL migration files in backend/db/migrations/
and records each one in the schema_migrations table so it's
never applied twice.

Usage
─────
  # Dry-run (print what would run, don't execute)
  python scripts/migrate.py --dry-run

  # Apply all pending migrations
  python scripts/migrate.py

  # Apply against a specific DATABASE_URL
  DATABASE_URL=<url> python scripts/migrate.py

Environment
───────────
  DATABASE_URL   – pooler connection string (port 6543)
                   Falls back to constructing from DATABASE_* parts.

Notes
─────
  • Uses psycopg 3 in synchronous mode (no async needed for a CLI tool).
  • prepare_threshold=0 is set so pgbouncer (Supabase pooler) doesn't
    reject prepared-statement commands.
  • Each migration is applied inside its own transaction; a failed
    migration rolls back and stops the script.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ── resolve repo root and add backend/ to sys.path ───────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "backend" / "db" / "migrations"
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

import psycopg  # noqa: E402  (after sys.path insert)


# ── helpers ───────────────────────────────────────────────────────────────────

def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    host = os.environ["DATABASE_HOST"]
    port = os.environ.get("DATABASE_PORT", "6543")
    name = os.environ.get("DATABASE_NAME", "postgres")
    user = os.environ["DATABASE_USER"]
    pwd = os.environ["DATABASE_PASSWORD"]
    from urllib.parse import quote_plus
    return f"postgresql://{user}:{quote_plus(pwd)}@{host}:{port}/{name}"


def migration_files() -> list[Path]:
    """Return migration .sql files sorted by their numeric prefix."""
    files = sorted(
        MIGRATIONS_DIR.glob("*.sql"),
        key=lambda p: int(re.match(r"^(\d+)", p.stem).group(1)),
    )
    return files


def ensure_migrations_table(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        create table if not exists schema_migrations (
            version    text primary key,
            applied_at timestamptz not null default now()
        )
        """
    )


def applied_versions(cur: psycopg.Cursor) -> set[str]:
    cur.execute("select version from schema_migrations")
    return {row[0] for row in cur.fetchall()}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Apply CodeDelta DB migrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pending migrations without executing them",
    )
    args = parser.parse_args()

    db_url = get_database_url()
    files = migration_files()

    if not files:
        print("No migration files found in", MIGRATIONS_DIR)
        return

    # psycopg 3 synchronous connection
    # prepare_threshold=0 disables server-side prepared statements,
    # required for Supabase's pgbouncer pooler (port 6543).
    conn_kwargs: dict = {
        "conninfo": db_url,
        "prepare_threshold": 0,
        "autocommit": False,
    }

    print(f"Connecting to database …")
    with psycopg.connect(**conn_kwargs) as conn:
        with conn.cursor() as cur:
            ensure_migrations_table(cur)
            conn.commit()
            already_applied = applied_versions(cur)

        pending = [f for f in files if f.stem not in already_applied]

        if not pending:
            print("✅  All migrations already applied.")
            return

        print(f"{'DRY-RUN — ' if args.dry_run else ''}Pending migrations:")
        for f in pending:
            print(f"  • {f.name}")

        if args.dry_run:
            print("\nDry-run complete. No changes made.")
            return

        for mf in pending:
            sql = mf.read_text(encoding="utf-8")
            print(f"\nApplying {mf.name} …", end=" ", flush=True)
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        cur.execute(
                            "insert into schema_migrations (version) values (%s)",
                            (mf.stem,),
                        )
                print("✅")
            except Exception as exc:  # noqa: BLE001
                print("❌")
                print(f"  Error: {exc}", file=sys.stderr)
                print("  Migration rolled back. Stopping.", file=sys.stderr)
                sys.exit(1)

    print("\n🎉  All migrations applied successfully.")


if __name__ == "__main__":
    main()
