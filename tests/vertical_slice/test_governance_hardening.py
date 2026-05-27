"""Governance and auth hardening tests."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from api.auth import UserRole, create_test_token
from api.main import app
from core.approval_service import create_immutable_proposal, prepare_approval_in_session, proposal_checksum
from core.governance_store import load_approval, save_approval
from core.runtime_session import run_mutative_session
from core.config import settings
from core.persistence import reset_in_memory_store
from core.policy import policy_engine
from core.runtime import RuntimeStateMachine
from schemas.runtime import RuntimeState


@pytest.mark.asyncio
async def test_mutating_endpoint_requires_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/founder/request", json={"message": "hello"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_readonly_cannot_prepare(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    token = create_test_token(role=UserRole.READONLY)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/actions/prepare",
            json={
                "correlation_id": "c1",
                "action": "create_initiative",
                "impact_summary": "test",
                "approval_level": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_expired_approval_rejected(monkeypatch):
    reset_in_memory_store()
    monkeypatch.setattr(settings, "auth_disabled", True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        prepare = await client.post(
            "/api/v1/actions/prepare",
            json={
                "correlation_id": "exp-corr",
                "action": "create_initiative",
                "parameters": {},
                "impact_summary": "expired test",
                "approval_level": 2,
            },
        )
        approval_id = prepare.json()["id"]

        async def _expire(conn):
            approval = await load_approval(conn, approval_id)
            assert approval is not None
            approval.immutable_proposal.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            approval.immutable_proposal.checksum = proposal_checksum(approval.immutable_proposal)
            await save_approval(conn, approval)

        await run_mutative_session("exp-corr", _expire)
        resp = await client.post(f"/api/v1/actions/approve/{approval_id}", json={"approved_by": "founder"})
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checksum_tamper_detected():
    proposal = create_immutable_proposal(
        correlation_id="c1",
        action="create_initiative",
        parameters={},
        agent="ceo",
        side_effect_level="EXECUTE_SAFE",
        impact_summary="tamper",
        proposed_by="founder",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    proposal.checksum = "deadbeef"
    with pytest.raises(ValueError, match="checksum"):
        await prepare_approval_in_session(proposal, "ceo")


@pytest.mark.asyncio
async def test_perceiving_to_escalated_transition():
    sm = RuntimeStateMachine(correlation_id="c", session_id="s")
    sm.start()
    sm.transition(RuntimeState.ESCALATED)
    assert sm.state == RuntimeState.ESCALATED
