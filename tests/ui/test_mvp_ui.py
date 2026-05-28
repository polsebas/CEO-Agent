"""UI integration tests for MVP operational console."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.auth import create_test_token
from api.main import app
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.roles import UserRole


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c


@pytest.mark.asyncio
async def test_login_page(client):
    r = await client.get("/login")
    assert r.status_code == 200
    assert "Ingreso operacional" in r.text


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "auth_disabled", False)
    r = await client.get("/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_with_token(client):
    token = create_test_token(role=UserRole.OPERATOR)
    r = await client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "Dashboard operacional" in r.text


@pytest.mark.asyncio
async def test_sessions_api_list(client):
    reset_in_memory_store()
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="ui-test-session",
        correlation_id="ui-test-corr",
    )
    token = create_test_token(role=UserRole.READONLY)
    r = await client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_session_detail_timeline(client):
    reset_in_memory_store()
    session_id = "ui-timeline-session"
    correlation_id = "ui-timeline-corr"
    await manual_orchestrator.run_founder_request(
        "Timeline test message",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.OPERATOR)
    r = await client.get(
        f"/sessions/{session_id}",
        params={"correlation_id": correlation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert session_id in r.text
    assert "timeline" in r.text.lower() or "Timeline" in r.text


@pytest.mark.asyncio
async def test_timeline_partial(client):
    reset_in_memory_store()
    session_id = "ui-partial-session"
    correlation_id = "ui-partial-corr"
    await manual_orchestrator.run_founder_request(
        "Partial timeline",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.OPERATOR)
    r = await client.get(
        f"/sessions/{session_id}/timeline",
        params={"correlation_id": correlation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_replay_view(client):
    reset_in_memory_store()
    session_id = "ui-replay-session"
    correlation_id = "ui-replay-corr"
    await manual_orchestrator.run_founder_request(
        "Replay view test",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.OPERATOR)
    r = await client.get(
        f"/sessions/{session_id}/replay",
        params={"correlation_id": correlation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "Replay inspector" in r.text


@pytest.mark.asyncio
async def test_diagnostics_view(client):
    reset_in_memory_store()
    session_id = "ui-diag-session"
    correlation_id = "ui-diag-corr"
    await manual_orchestrator.run_founder_request(
        "Diagnostics view test",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.READONLY)
    r = await client.get(
        f"/sessions/{session_id}/diagnostics",
        params={"correlation_id": correlation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "Diagnostics" in r.text


@pytest.mark.asyncio
async def test_approvals_page(client):
    token = create_test_token(role=UserRole.REVIEWER)
    r = await client.get("/approvals", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "aprobaciones" in r.text.lower()


@pytest.mark.asyncio
async def test_session_export(client):
    reset_in_memory_store()
    session_id = "ui-export-session"
    correlation_id = "ui-export-corr"
    await manual_orchestrator.run_founder_request(
        "Export test",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.OPERATOR)
    r = await client.get(
        f"/sessions/{session_id}/export",
        params={"correlation_id": correlation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    assert b"human_summaries" in r.content
