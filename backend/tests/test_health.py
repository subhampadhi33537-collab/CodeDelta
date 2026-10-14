"""Pytest smoke test for the health endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_health_ok(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "CodeDelta"
    assert "timestamp" in body


async def test_health_has_version(client: AsyncClient):
    response = await client.get("/api/health")
    body = response.json()
    assert "version" in body
    assert body["version"] != ""
