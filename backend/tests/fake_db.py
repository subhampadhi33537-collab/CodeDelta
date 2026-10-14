"""
backend/tests/fake_db.py
────────────────────────
In-memory async connection implementation for deterministic repository and API tests.
Mocks the psycopg 3 AsyncConnection and AsyncCursor interface.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class InMemoryDatabase:
    """Stores tables in memory."""

    def __init__(self):
        self.users: Dict[UUID, Dict[str, Any]] = {}
        self.projects: Dict[UUID, Dict[str, Any]] = {}
        self.versions: Dict[UUID, Dict[str, Any]] = {}
        self.runs: Dict[UUID, Dict[str, Any]] = {}
        self.events: List[Dict[str, Any]] = []
        self._event_id_seq = 1

    def clear(self):
        self.users.clear()
        self.projects.clear()
        self.versions.clear()
        self.runs.clear()
        self.events.clear()
        self._event_id_seq = 1


class FakeAsyncCursor:
    def __init__(self, db: InMemoryDatabase):
        self.db = db
        self._last_result: List[Dict[str, Any]] = []
        self.rowcount: int = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query: str, params: tuple | list = ()):
        q = " ".join(query.strip().split())
        params = list(params) if params else []
        self._last_result = []
        self.rowcount = 0

        # ── USERS ─────────────────────────────────────────────────────────────
        if q.startswith("insert into users"):
            name, email, pwd_hash = params[0], params[1], params[2]
            uid = uuid4()
            now = datetime.now(timezone.utc)
            row = {
                "id": uid,
                "name": name,
                "email": email.lower(),
                "password_hash": pwd_hash,
                "drive_folder_id": None,
                "is_active": True,
                "created_at": now,
            }
            self.db.users[uid] = row
            self._last_result = [row]
            self.rowcount = 1

        elif q.startswith("select id, name, email, password_hash, drive_folder_id, is_active, created_at from users where id = %s"):
            uid = UUID(str(params[0]))
            user = self.db.users.get(uid)
            if user:
                self._last_result = [user]

        elif q.startswith("select id, name, email, password_hash, drive_folder_id, is_active, created_at from users where email = %s"):
            email_target = str(params[0]).strip().lower()
            found = [u for u in self.db.users.values() if u["email"].lower() == email_target]
            if found:
                self._last_result = [found[0]]

        elif q.startswith("update users set drive_folder_id = %s where id = %s"):
            folder_id, uid = params[0], UUID(str(params[1]))
            user = self.db.users.get(uid)
            if user:
                user["drive_folder_id"] = folder_id
                self._last_result = [user]
                self.rowcount = 1

        # ── PROJECTS ──────────────────────────────────────────────────────────
        elif q.startswith("insert into projects"):
            uid, name, prompt = UUID(str(params[0])), params[1], params[2]
            pid = uuid4()
            now = datetime.now(timezone.utc)
            row = {
                "id": pid,
                "user_id": uid,
                "name": name,
                "initial_prompt": prompt,
                "status": "draft",
                "current_version": 0,
                "created_at": now,
                "updated_at": now,
            }
            self.db.projects[pid] = row
            self._last_result = [row]
            self.rowcount = 1

        elif q.startswith("select id, user_id, name, initial_prompt, status, current_version, created_at, updated_at from projects where id = %s and user_id = %s"):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            proj = self.db.projects.get(pid)
            if proj and proj["user_id"] == uid:
                self._last_result = [proj]

        elif q.startswith("select id, user_id, name, initial_prompt, status, current_version, created_at, updated_at from projects where user_id = %s"):
            uid, limit, offset = UUID(str(params[0])), int(params[1]), int(params[2])
            matching = [p for p in self.db.projects.values() if p["user_id"] == uid]
            matching.sort(key=lambda x: x["updated_at"], reverse=True)
            self._last_result = matching[offset : offset + limit]

        elif q.startswith("update projects set"):
            pid, uid = UUID(str(params[-2])), UUID(str(params[-1]))
            proj = self.db.projects.get(pid)
            if proj and proj["user_id"] == uid:
                idx = 0
                if "name = %s" in q:
                    proj["name"] = params[idx]; idx += 1
                if "status = %s" in q:
                    proj["status"] = params[idx]; idx += 1
                if "current_version = %s" in q:
                    proj["current_version"] = params[idx]; idx += 1
                proj["updated_at"] = datetime.now(timezone.utc)
                self._last_result = [proj]
                self.rowcount = 1

        elif q.startswith("delete from projects where id = %s and user_id = %s"):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            proj = self.db.projects.get(pid)
            if proj and proj["user_id"] == uid:
                del self.db.projects[pid]
                self.rowcount = 1

        # ── PROJECT VERSIONS ──────────────────────────────────────────────────
        elif q.startswith("insert into project_versions"):
            pid = UUID(str(params[0]))
            uid = UUID(str(params[1]))
            ver = int(params[2])
            df_id = params[3]
            sz = params[4]
            sha = params[5]
            run_id = UUID(str(params[6])) if params[6] else None
            vid = uuid4()
            now = datetime.now(timezone.utc)
            row = {
                "id": vid,
                "project_id": pid,
                "user_id": uid,
                "version": ver,
                "drive_file_id": df_id,
                "size_bytes": sz,
                "sha256": sha,
                "run_id": run_id,
                "created_at": now,
            }
            self.db.versions[vid] = row
            self._last_result = [row]
            self.rowcount = 1

        elif q.startswith("select id, project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id, created_at from project_versions where project_id = %s and user_id = %s and version = %s"):
            pid, uid, ver = UUID(str(params[0])), UUID(str(params[1])), int(params[2])
            matching = [v for v in self.db.versions.values() if v["project_id"] == pid and v["user_id"] == uid and v["version"] == ver]
            if matching:
                self._last_result = [matching[0]]

        elif q.startswith("select id, project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id, created_at from project_versions where project_id = %s and user_id = %s order by version desc"):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            matching = [v for v in self.db.versions.values() if v["project_id"] == pid and v["user_id"] == uid]
            matching.sort(key=lambda x: x["version"], reverse=True)
            self._last_result = matching

        elif "delete from project_versions" in q and "keep_count" in str(params):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            keep = int(params[-1])
            vers = [v for v in self.db.versions.values() if v["project_id"] == pid and v["user_id"] == uid]
            vers.sort(key=lambda x: x["version"], reverse=True)
            to_delete = vers[keep:]
            deleted_rows = []
            for item in to_delete:
                del self.db.versions[item["id"]]
                deleted_rows.append({"drive_file_id": item["drive_file_id"]})
            self._last_result = deleted_rows
            self.rowcount = len(deleted_rows)

        # ── RUNS ──────────────────────────────────────────────────────────────
        elif q.startswith("insert into agent_runs"):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            intent, model_choice = params[2], params[3]
            rid = uuid4()
            now = datetime.now(timezone.utc)
            row = {
                "id": rid,
                "project_id": pid,
                "user_id": uid,
                "intent": intent,
                "status": "queued",
                "model_choice": model_choice,
                "error": None,
                "started_at": None,
                "ended_at": None,
                "created_at": now,
            }
            self.db.runs[rid] = row
            self._last_result = [row]
            self.rowcount = 1

        elif q.startswith("select id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at from agent_runs where id = %s and user_id = %s"):
            rid, uid = UUID(str(params[0])), UUID(str(params[1]))
            r = self.db.runs.get(rid)
            if r and r["user_id"] == uid:
                self._last_result = [r]

        elif q.startswith("update agent_runs set"):
            rid = UUID(str(params[-1]))
            r = self.db.runs.get(rid)
            if r:
                r["status"] = params[0]
                idx = 1
                if "error = %s" in q:
                    r["error"] = params[idx]; idx += 1
                if "started_at = %s" in q:
                    r["started_at"] = params[idx]; idx += 1
                if "ended_at = %s" in q:
                    r["ended_at"] = params[idx]; idx += 1
                self._last_result = [r]
                self.rowcount = 1

        elif q.startswith("select id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at from agent_runs where project_id = %s and user_id = %s"):
            pid, uid = UUID(str(params[0])), UUID(str(params[1]))
            matching = [r for r in self.db.runs.values() if r["project_id"] == pid and r["user_id"] == uid]
            matching.sort(key=lambda x: x["created_at"], reverse=True)
            self._last_result = matching

        # ── EVENTS ────────────────────────────────────────────────────────────
        elif q.startswith("insert into agent_events"):
            rid, seq, agent, ev_type, p_json = (
                UUID(str(params[0])),
                int(params[1]),
                params[2],
                params[3],
                params[4],
            )
            payload = json.loads(p_json) if p_json else None
            now = datetime.now(timezone.utc)
            eid = self.db._event_id_seq
            self.db._event_id_seq += 1
            row = {
                "id": eid,
                "run_id": rid,
                "seq": seq,
                "agent": agent,
                "type": ev_type,
                "payload": payload,
                "created_at": now,
            }
            self.db.events.append(row)
            self._last_result = [row]
            self.rowcount = 1

        elif q.startswith("select id, run_id, seq, agent, type, payload, created_at from agent_events where run_id = %s and seq > %s"):
            rid, after_seq = UUID(str(params[0])), int(params[1])
            matching = [e for e in self.db.events if e["run_id"] == rid and e["seq"] > after_seq]
            matching.sort(key=lambda x: x["seq"])
            self._last_result = matching

    async def fetchone(self) -> Optional[Dict[str, Any]]:
        return self._last_result[0] if self._last_result else None

    async def fetchall(self) -> List[Dict[str, Any]]:
        return list(self._last_result)


class FakeAsyncConnection:
    """Mock psycopg 3 connection for in-memory testing."""

    def __init__(self, db: Optional[InMemoryDatabase] = None):
        self.db = db if db is not None else InMemoryDatabase()

    def cursor(self) -> FakeAsyncCursor:
        return FakeAsyncCursor(self.db)

    async def commit(self):
        pass

    async def rollback(self):
        pass
