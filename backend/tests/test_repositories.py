"""
backend/tests/test_repositories.py
──────────────────────────────────
Unit tests for database repositories using the fake async connection:
- users
- projects
- versions
- runs
- events
- tenant isolation (User A cannot access User B's resources)
"""

from __future__ import annotations

from uuid import uuid4
import pytest

from app.db.repositories.events import append_event, list_events_by_run
from app.db.repositories.projects import (
    create_project,
    delete_project,
    get_project_by_id,
    list_projects_by_user,
    update_project,
)
from app.db.repositories.runs import (
    create_run,
    get_run_by_id,
    list_runs_by_project,
    update_run_status,
)
from app.db.repositories.users import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_drive_folder,
)
from app.db.repositories.versions import (
    create_version,
    delete_older_versions,
    get_version,
    list_versions_by_project,
)
from tests.fake_db import FakeAsyncConnection, InMemoryDatabase


@pytest.fixture
def conn() -> FakeAsyncConnection:
    return FakeAsyncConnection(InMemoryDatabase())


@pytest.mark.asyncio
async def test_user_repository(conn: FakeAsyncConnection):
    # 1. Create user
    user = await create_user(
        conn,
        name="Alice Tester",
        email="Alice@Example.Com",
        password_hash="$argon2id$fakehash123",
    )
    assert user.id is not None
    assert user.name == "Alice Tester"
    assert user.email == "alice@example.com"
    assert user.is_active is True
    assert user.drive_folder_id is None

    # 2. Get by ID
    by_id = await get_user_by_id(conn, user.id)
    assert by_id is not None
    assert by_id.id == user.id
    assert by_id.email == "alice@example.com"

    # 3. Get by Email (case-insensitive)
    by_email = await get_user_by_email(conn, "ALICE@example.com")
    assert by_email is not None
    assert by_email.id == user.id

    # 4. Unknown email returns None
    assert await get_user_by_email(conn, "bob@example.com") is None

    # 5. Update drive folder id
    updated = await update_user_drive_folder(conn, user.id, "folder_12345")
    assert updated is not None
    assert updated.drive_folder_id == "folder_12345"


@pytest.mark.asyncio
async def test_project_repository(conn: FakeAsyncConnection):
    user_a = await create_user(conn, "User A", "a@test.com", "hash_a")
    user_b = await create_user(conn, "User B", "b@test.com", "hash_b")

    # 1. Create project for user A
    proj = await create_project(
        conn,
        user_id=user_a.id,
        name="Portfolio Website",
        initial_prompt="Build a sleek personal portfolio",
    )
    assert proj.id is not None
    assert proj.user_id == user_a.id
    assert proj.name == "Portfolio Website"
    assert proj.status == "draft"
    assert proj.current_version == 0

    # 2. User A can retrieve project
    retrieved = await get_project_by_id(conn, proj.id, user_a.id)
    assert retrieved is not None
    assert retrieved.id == proj.id

    # 3. User B CANNOT retrieve User A's project (tenant isolation -> None)
    cross_user = await get_project_by_id(conn, proj.id, user_b.id)
    assert cross_user is None

    # 4. List projects by user
    projs_a = await list_projects_by_user(conn, user_a.id)
    assert len(projs_a) == 1
    assert projs_a[0].id == proj.id

    projs_b = await list_projects_by_user(conn, user_b.id)
    assert len(projs_b) == 0

    # 5. Update project
    up = await update_project(
        conn,
        project_id=proj.id,
        user_id=user_a.id,
        name="Updated Portfolio",
        status="building",
        current_version=1,
    )
    assert up is not None
    assert up.name == "Updated Portfolio"
    assert up.status == "building"
    assert up.current_version == 1

    # 6. Delete project
    deleted = await delete_project(conn, proj.id, user_a.id)
    assert deleted is True
    assert await get_project_by_id(conn, proj.id, user_a.id) is None


@pytest.mark.asyncio
async def test_versions_repository(conn: FakeAsyncConnection):
    user = await create_user(conn, "Alice", "alice@v.com", "hash")
    proj = await create_project(conn, user.id, "App", "Prompt")

    # 1. Create versions
    v1 = await create_version(
        conn,
        project_id=proj.id,
        user_id=user.id,
        version=1,
        drive_file_id="drive_file_v1",
        size_bytes=1024,
        sha256="abc123sha",
    )
    assert v1.version == 1
    assert v1.drive_file_id == "drive_file_v1"

    v2 = await create_version(
        conn,
        project_id=proj.id,
        user_id=user.id,
        version=2,
        drive_file_id="drive_file_v2",
        size_bytes=2048,
        sha256="def456sha",
    )
    assert v2.version == 2

    # 2. Get specific version
    found_v1 = await get_version(conn, proj.id, user.id, 1)
    assert found_v1 is not None
    assert found_v1.version == 1
    assert found_v1.drive_file_id == "drive_file_v1"

    # 3. List versions ordered desc
    versions = await list_versions_by_project(conn, proj.id, user.id)
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1

    # 4. Another user cannot see versions
    other_user_id = uuid4()
    assert await get_version(conn, proj.id, other_user_id, 1) is None
    assert len(await list_versions_by_project(conn, proj.id, other_user_id)) == 0


@pytest.mark.asyncio
async def test_runs_and_events_repository(conn: FakeAsyncConnection):
    user = await create_user(conn, "Alice", "alice@runs.com", "hash")
    proj = await create_project(conn, user.id, "App", "Prompt")

    # 1. Create run
    run = await create_run(
        conn,
        project_id=proj.id,
        user_id=user.id,
        intent="create",
        model_choice="llama-3.3-70b-versatile",
    )
    assert run.id is not None
    assert run.status == "queued"
    assert run.model_choice == "llama-3.3-70b-versatile"

    # 2. Get run
    r = await get_run_by_id(conn, run.id, user.id)
    assert r is not None
    assert r.id == run.id

    # Cross user access returns None
    assert await get_run_by_id(conn, run.id, uuid4()) is None

    # 3. Update status
    updated_run = await update_run_status(conn, run.id, status="running")
    assert updated_run is not None
    assert updated_run.status == "running"

    # 4. Append events
    e1 = await append_event(
        conn,
        run_id=run.id,
        seq=1,
        event_type="plan_started",
        agent="planner",
        payload={"task": "Scaffold UI"},
    )
    assert e1.seq == 1
    assert e1.type == "plan_started"
    assert e1.payload == {"task": "Scaffold UI"}

    e2 = await append_event(
        conn,
        run_id=run.id,
        seq=2,
        event_type="code_generated",
        agent="coder",
        payload={"file": "index.html"},
    )
    assert e2.seq == 2

    # 5. List events with seq filtering
    all_events = await list_events_by_run(conn, run.id, after_seq=0)
    assert len(all_events) == 2
    assert all_events[0].seq == 1
    assert all_events[1].seq == 2

    after_seq_events = await list_events_by_run(conn, run.id, after_seq=1)
    assert len(after_seq_events) == 1
    assert after_seq_events[0].seq == 2
