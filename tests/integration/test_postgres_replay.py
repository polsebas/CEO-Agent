"""Postgres frozen/live replay integration — RRM1.5-M4."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.frozen_replay_executor import frozen_replay_executor
from core.live_replay_adapter import live_replay_adapter
from core.orchestrator import manual_orchestrator
from core.persistence import get_pool, get_replay_baseline_meta, get_runtime_transitions
from core.replay import replay_engine
from core.replay_validator import validate_frozen_replay
from schemas.replay import outcome_fingerprint
from schemas.runtime import ReplayMode


@pytest.mark.postgres
@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_postgres_frozen_replay_matches_baseline(postgres_available):
    session_id = f"pg-replay-{uuid4()}"
    correlation_id = f"pg-replay-corr-{uuid4()}"
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert "error" not in result

    ok, fp, baseline = await validate_frozen_replay(session_id, correlation_id)
    assert baseline is not None
    assert fp == baseline
    assert ok is True

    meta = await get_replay_baseline_meta(session_id)
    assert meta is not None
    assert meta.get("orchestrator_version") == frozen_replay_executor.ORCHESTRATOR_VERSION


@pytest.mark.postgres
@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_postgres_frozen_executor_with_conn(postgres_available):
    session_id = f"pg-exec-{uuid4()}"
    correlation_id = f"pg-exec-corr-{uuid4()}"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )

    pool = await get_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        transitions = await get_runtime_transitions(session_id, conn=conn)
        assert len(transitions) >= 1
        bundle = await frozen_replay_executor.load_bundle(
            session_id, correlation_id, conn=conn
        )
        outcome = await frozen_replay_executor.run(bundle, conn=conn)

    baseline = (await get_replay_baseline_meta(session_id))["outcome_fingerprint"]
    assert outcome_fingerprint(outcome) == baseline


@pytest.mark.postgres
@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_postgres_live_replay_stable_tools(postgres_available):
    session_id = f"pg-live-{uuid4()}"
    correlation_id = f"pg-live-corr-{uuid4()}"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )

    session = await replay_engine.replay_session(
        session_id, correlation_id, ReplayMode.LIVE
    )
    assert session.outcome_match is True
    assert session.world_state_snapshot.get("replay_source") == "live_tool_adapter"

    pool = await get_pool()
    async with pool.acquire() as conn:
        live_outcome = await live_replay_adapter.run_live_outcome(
            session_id, correlation_id, conn=conn
        )
    meta = await get_replay_baseline_meta(session_id)
    assert outcome_fingerprint(live_outcome) == meta["outcome_fingerprint"]
