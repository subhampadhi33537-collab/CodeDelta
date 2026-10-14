"""
backend/tests/test_auth.py
──────────────────────────
Comprehensive integration tests for authentication (Phase 2):
- Valid register
- Bad email (422)
- Weak password: < 8 chars, no digit, no letter (422)
- Blank name & short name (422)
- Duplicate email (409)
- Login success
- Login wrong password (generic 401)
- Login unknown email (generic 401)
- GET /api/auth/me with valid token
- Missing token (401)
- Expired token (401)
- Tampered token (401)
- Security headers present
- No password hash ever appears in responses
- Another user's resource isolation / 404
"""

from __future__ import annotations

import time
from uuid import uuid4
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.db.pool import get_db_connection
from app.db.repositories.projects import create_project, get_project_by_id
from app.dependencies import get_current_user
from app.main import app
from tests.fake_db import FakeAsyncConnection, InMemoryDatabase


@pytest.fixture
def fake_db() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def fake_conn(fake_db: InMemoryDatabase) -> FakeAsyncConnection:
    return FakeAsyncConnection(fake_db)


@pytest.fixture
def client(fake_conn: FakeAsyncConnection):
    # Override get_db_connection dependency to use our in-memory fake connection
    async def override_get_db_connection():
        yield fake_conn

    app.dependency_overrides[get_db_connection] = override_get_db_connection
    transport = ASGITransport(app=app)
    test_client = AsyncClient(transport=transport, base_url="http://test")
    yield test_client
    app.dependency_overrides.clear()


def assert_no_hashes_in_data(data: dict | list | str):
    """Recursively verify no password hash or credential string is exposed."""
    if isinstance(data, dict):
        for k, v in data.items():
            assert "hash" not in k.lower(), f"Suspicious key in response: {k}"
            assert "password" not in k.lower(), f"Password key exposed in response: {k}"
            assert_no_hashes_in_data(v)
    elif isinstance(data, list):
        for item in data:
            assert_no_hashes_in_data(item)
    elif isinstance(data, str):
        assert not data.startswith("$argon2"), f"Argon2 hash leaked in response: {data}"


# ── TEST CASES ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_register(client: AsyncClient):
    payload = {
        "name": "Subham Padhi",
        "email": "subham@example.com",
        "password": "SecurePassword123!",
    }
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["name"] == "Subham Padhi"
    assert data["user"]["email"] == "subham@example.com"
    assert "id" in data["user"]

    assert_no_hashes_in_data(data)


@pytest.mark.asyncio
async def test_bad_email(client: AsyncClient):
    payload = {
        "name": "Invalid Email User",
        "email": "not-a-valid-email",
        "password": "ValidPassword123",
    }
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_weak_password(client: AsyncClient):
    # Too short (< 8)
    res = await client.post("/api/auth/register", json={
        "name": "Short Pass",
        "email": "short@example.com",
        "password": "Pass1",
    })
    assert res.status_code == 422

    # No digit
    res = await client.post("/api/auth/register", json={
        "name": "No Digit",
        "email": "nodigit@example.com",
        "password": "PasswordOnlyLetters",
    })
    assert res.status_code == 422

    # No letter
    res = await client.post("/api/auth/register", json={
        "name": "No Letter",
        "email": "noletter@example.com",
        "password": "1234567890123",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_blank_name(client: AsyncClient):
    # Blank whitespace
    res = await client.post("/api/auth/register", json={
        "name": "   ",
        "email": "blank@example.com",
        "password": "ValidPassword123",
    })
    assert res.status_code == 422

    # Too short (< 2)
    res = await client.post("/api/auth/register", json={
        "name": "A",
        "email": "shortname@example.com",
        "password": "ValidPassword123",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient):
    payload = {
        "name": "First User",
        "email": "duplicate@example.com",
        "password": "ValidPassword123",
    }
    # First registration succeeds
    res1 = await client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with same email (even with different casing) fails with 409
    payload2 = {
        "name": "Second User",
        "email": "DUPLICATE@EXAMPLE.COM",
        "password": "AnotherPassword456",
    }
    res2 = await client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # 1. Register
    reg_payload = {
        "name": "Login Tester",
        "email": "login@example.com",
        "password": "MySecretPassword99",
    }
    await client.post("/api/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "email": "LOGIN@EXAMPLE.COM",  # case insensitivity
        "password": "MySecretPassword99",
    }
    res = await client.post("/api/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login@example.com"
    assert_no_hashes_in_data(data)


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    # Register
    await client.post("/api/auth/register", json={
        "name": "Login Tester",
        "email": "wrongpass@example.com",
        "password": "CorrectPassword123",
    })

    # Wrong password -> generic 401
    res = await client.post("/api/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "WrongPassword999",
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    # Non-existent user -> generic 401
    res = await client.post("/api/auth/login", json={
        "email": "ghost@example.com",
        "password": "SomePassword123",
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient):
    # Register to get token
    reg_res = await client.post("/api/auth/register", json={
        "name": "Me Tester",
        "email": "me@example.com",
        "password": "SecurePassword123",
    })
    token = reg_res.json()["access_token"]

    # GET /api/auth/me with Bearer token
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Me Tester"
    assert data["email"] == "me@example.com"
    assert "id" in data
    assert_no_hashes_in_data(data)


@pytest.mark.asyncio
async def test_get_me_missing_token(client: AsyncClient):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_expired_token(client: AsyncClient):
    settings = get_settings()
    # Create an expired token manually
    expired_payload = {
        "sub": str(uuid4()),
        "email": "expired@example.com",
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 1800,  # expired 30 mins ago
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm="HS256")

    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_me_tampered_token(client: AsyncClient):
    # Register to get valid token
    reg_res = await client.post("/api/auth/register", json={
        "name": "Tamper Tester",
        "email": "tamper@example.com",
        "password": "SecurePassword123",
    })
    token = reg_res.json()["access_token"]

    # Tamper token signature
    tampered_token = token[:-5] + "XXXXX"

    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"


@pytest.mark.asyncio
async def test_another_user_resource_returns_404(client: AsyncClient, fake_conn: FakeAsyncConnection):
    """Verify that User B cannot query or load User A's project."""
    # 1. Register User A
    res_a = await client.post("/api/auth/register", json={
        "name": "User A",
        "email": "usera@example.com",
        "password": "PasswordUserA1",
    })
    user_a_id = res_a.json()["user"]["id"]

    # 2. Register User B
    res_b = await client.post("/api/auth/register", json={
        "name": "User B",
        "email": "userb@example.com",
        "password": "PasswordUserB1",
    })
    user_b_id = res_b.json()["user"]["id"]

    # User A creates a project directly in repo
    proj = await create_project(
        fake_conn,
        user_id=user_a_id,
        name="User A Secret Project",
        initial_prompt="Secret prompt",
    )

    # When User B attempts to access User A's project with User B's user_id:
    accessed = await get_project_by_id(fake_conn, proj.id, user_b_id)
    assert accessed is None  # Repository enforces tenant isolation, returning None (yielding 404 in route)
