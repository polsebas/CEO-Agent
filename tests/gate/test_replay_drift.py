import copy
from unittest.mock import patch

import pytest

from core.live_replay_adapter import LiveToolReplayAdapter, live_replay_adapter
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.replay import replay_engine
from core.replay_store import get_replay_snapshots_memory
from schemas.runtime import ReplayMode
from schemas.tools import ToolResult
from tools.router import execute_tool


@pytest.mark.asyncio
async def test_live_replay_detects_drift():
    reset_in_memory_store()
    session_id = "drift-session"
    correlation_id = "drift-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    before = copy.deepcopy(get_replay_snapshots_memory(session_id))

    original_execute = execute_tool

    async def drifted_execute(tool_name, agent_id, correlation_id, params=None):
        result = await original_execute(tool_name, agent_id, correlation_id, params)
        return result.model_copy(update={"tool_name": "mutated_tool"})

    adapter = LiveToolReplayAdapter(tool_executor=drifted_execute)
    with patch("core.replay.live_replay_adapter", adapter):
        session = await replay_engine.replay_session(
            session_id,
            correlation_id,
            ReplayMode.LIVE,
        )

    assert session.outcome_match is False
    assert session.world_state_snapshot.get("drift_fields")
    assert session.world_state_snapshot.get("replay_source") == "live_tool_adapter"
    assert get_replay_snapshots_memory(session_id) == before


@pytest.mark.asyncio
async def test_frozen_replay_matches_baseline_ten_times():
    reset_in_memory_store()
    session_id = "baseline-ten"
    correlation_id = "baseline-ten-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    fingerprints = []
    for _ in range(10):
        session = await replay_engine.replay_session(session_id, correlation_id, ReplayMode.FROZEN)
        assert session.outcome_match is True
        fingerprints.append(session.world_state_snapshot.get("outcome_fingerprint"))
    assert len(set(fingerprints)) == 1
