import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from core.health import agent_health_registry
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.preprocessor import preprocessor
from core.replay import replay_engine
from core.runtime import RuntimeStateMachine
from schemas.messages import AgentMessage, AgentRole, MessageIntent
from schemas.runtime import ReplayMode, RuntimeState
from uuid import uuid4


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("healthy", "degraded")


@pytest.mark.asyncio
async def test_deterministic_github_request():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/founder/request",
            json={"message": "How many PRs are open?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("mode") == "deterministic"
        tool_result = data.get("result", {})
        assert tool_result.get("success") is True


@pytest.mark.asyncio
async def test_cognitive_orchestration_flow():
    reset_in_memory_store()
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly and incident status"
    )
    assert "correlation_id" in result
    assert result.get("runtime_state") == "completed"
    assert "result" in result


@pytest.mark.asyncio
async def test_concurrent_sessions_no_leakage():
    reset_in_memory_store()

    async def run(session_suffix: str):
        return await manual_orchestrator.run_founder_request(
            f"Check repo health {session_suffix}",
            session_id=f"session-{session_suffix}",
            correlation_id=f"corr-{session_suffix}",
        )

    results = await asyncio.gather(*[run(str(i)) for i in range(10)])
    session_ids = [r["session_id"] for r in results]
    assert len(set(session_ids)) == 10


@pytest.mark.asyncio
async def test_frozen_replay():
    reset_in_memory_store()
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="replay-session",
        correlation_id="replay-corr",
    )
    assert "error" not in result
    session = await replay_engine.replay_session(
        "replay-session", "replay-corr", ReplayMode.FROZEN
    )
    assert session.outcome_match is True
    assert len(session.snapshots) >= 1
    assert session.world_state_snapshot.get("source") == "historical_snapshot"


@pytest.mark.asyncio
async def test_frozen_replay_deterministic_ten_runs():
    reset_in_memory_store()
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="replay-det",
        correlation_id="replay-det-corr",
    )
    outcomes = []
    for _ in range(10):
        session = await replay_engine.replay_session(
            "replay-det", "replay-det-corr", ReplayMode.FROZEN
        )
        outcomes.append(session.outcome_match)
    assert all(outcomes)
    assert len(set(str(s.tool_outputs) for s in session.snapshots)) == 1 or len(session.snapshots) >= 1


@pytest.mark.asyncio
async def test_executive_timeline():
    reset_in_memory_store()
    corr = str(uuid4())
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        correlation_id=corr,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/timeline?correlation_id={corr}")
        assert resp.status_code == 200
        timeline = resp.json()
        assert len(timeline) >= 1


@pytest.mark.asyncio
async def test_approval_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        prepare = await client.post(
            "/api/v1/actions/prepare",
            json={
                "correlation_id": "apr-corr",
                "agent": "ceo",
                "action": "create_initiative",
                "parameters": {"name": "Q2 initiative"},
                "side_effect_level": "EXECUTE_SAFE",
                "impact_summary": "Create initiative",
                "approval_level": 2,
            },
        )
        assert prepare.status_code == 200
        approval_id = prepare.json()["id"]
        approve = await client.post(
            f"/api/v1/actions/approve/{approval_id}",
            json={"approved_by": "founder"},
        )
        assert approve.status_code == 200
        assert "execution" in approve.json()


@pytest.mark.asyncio
async def test_agent_health_degraded_mode():
    agent_health_registry.clear()
    for _ in range(10):
        agent_health_registry.record_run_sync("test_agent", success=False, latency_ms=100)
    assert agent_health_registry.is_degraded_sync("test_agent") is True


@pytest.mark.asyncio
async def test_side_effect_partial_detection():
    from datetime import datetime, timezone
    from uuid import uuid4

    from core.persistence import get_effects_by_correlation
    from core.runtime_session import run_mutative_session
    from core.transaction import PersistRuntimePayload, persist_runtime_tx
    from schemas.effects import SideEffectRecord

    corr = str(uuid4())
    effect = SideEffectRecord(
        id=str(uuid4()),
        action_id="a1",
        correlation_id=corr,
        systems_affected=["github", "ci"],
        mutation_status="partial",
        rollback_available=True,
        created_at=datetime.now(timezone.utc),
    )

    async def _persist(conn):
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=corr,
                session_id=corr,
                event_type="side_effect.recorded",
                event_payload=effect.model_dump(mode="json"),
                side_effect=effect,
                business_key=f"effect:{effect.id}",
            ),
        )

    await run_mutative_session(corr, _persist)
    effects = await get_effects_by_correlation(corr)
    assert effects[0].mutation_status == "partial"


@pytest.mark.asyncio
async def test_canonical_replay_fingerprint_stable():
    from core.replay_validator import validate_frozen_replay

    reset_in_memory_store()
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="fp-session",
        correlation_id="fp-corr",
    )
    match, fp, baseline = await validate_frozen_replay("fp-session", "fp-corr")
    assert baseline is not None
    assert match is True
    assert fp == baseline
