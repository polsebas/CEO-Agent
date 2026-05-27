"""RRM-2E — replay analytics gate."""

from __future__ import annotations

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.replay_analytics import analyze_replay
from schemas.runtime import ReplayMode


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_replay_analytics_frozen_deterministic():
    reset_in_memory_store()
    session_id = "rrm2-replay-a"
    correlation_id = "rrm2-replay-a-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    a1 = await analyze_replay(session_id, correlation_id, mode=ReplayMode.FROZEN)
    a2 = await analyze_replay(session_id, correlation_id, mode=ReplayMode.FROZEN)
    assert a1.replay_confidence == a2.replay_confidence
    assert a1.outcome_match == a2.outcome_match
    assert a1.outcome_match is True


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_replay_analytics_api_shape():
    reset_in_memory_store()
    from core.diagnostics import diagnostics_service

    session_id = "rrm2-replay-b"
    correlation_id = "rrm2-replay-b-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    analytics = await diagnostics_service.get_replay_analysis(
        session_id, correlation_id, mode=ReplayMode.FROZEN
    )
    assert analytics.orchestration_version
    assert analytics.replay_confidence >= 0.0
