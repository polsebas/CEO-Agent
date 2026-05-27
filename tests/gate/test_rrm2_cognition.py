"""RRM-2B — cognitive telemetry gate."""

from __future__ import annotations

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import query_cognitive_telemetry, reset_in_memory_store
from core.prompt_lineage import prompt_lineage_tracker
from schemas.cognition import PromptLineage


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_cognitive_telemetry_persisted():
    reset_in_memory_store()
    session_id = "rrm2-cog"
    correlation_id = "rrm2-cog-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    rows = await query_cognitive_telemetry(session_id, correlation_id=correlation_id)
    assert len(rows) >= 1
    assert rows[0].token_estimate > 0
    assert rows[0].reasoning_latency_ms >= 0


@pytest.mark.rrm2
def test_prompt_lineage_chain():
    prompt_lineage_tracker.reset_session("s1")
    l1 = prompt_lineage_tracker.build(
        prompt="first prompt",
        session_id="s1",
        correlation_id="c1",
    )
    l2 = prompt_lineage_tracker.build(
        prompt="second prompt",
        session_id="s1",
        correlation_id="c1",
    )
    assert l2.parent_prompt_hash == l1.prompt_hash
    assert len(l1.prompt_hash) == 64


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_lineage_in_persisted_snapshots():
    reset_in_memory_store()
    from core.persistence import get_replay_snapshots

    session_id = "rrm2-lineage"
    correlation_id = "rrm2-lineage-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly with github incidents",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    snaps = await get_replay_snapshots(session_id)
    assert any(s.get("context_fingerprint") for s in snaps)
