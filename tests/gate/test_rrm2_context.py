"""RRM-2D — context lifecycle gate."""

from __future__ import annotations

import pytest

from core.context import ContextWindowManager
from core.context_lifecycle import context_lifecycle
from core.persistence import get_replay_snapshots, reset_in_memory_store
from core.orchestrator import manual_orchestrator
from schemas.context import ContextFingerprint


@pytest.mark.rrm2
def test_compression_lineage_reproducible():
    layers = {"L4": "x" * 2000}
    s1, e1 = context_lifecycle.summarize_old_context(layers)
    s2, e2 = context_lifecycle.summarize_old_context(layers)
    assert s1 == s2
    assert e1 == e2


@pytest.mark.rrm2
def test_budget_enforcement():
    fp = ContextFingerprint(context_hash="h", token_utilization=1.5)
    assert context_lifecycle.enforce_budget(fp.token_utilization, 8000, 5000) is False


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_context_fingerprint_v2_on_snapshots():
    reset_in_memory_store()
    session_id = "rrm2-ctx"
    correlation_id = "rrm2-ctx-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    snaps = await get_replay_snapshots(session_id)
    fps = [s["context_fingerprint"] for s in snaps if s.get("context_fingerprint")]
    assert fps
    assert "context_hash" in fps[0]


@pytest.mark.rrm2
def test_summarize_trigger_deterministic():
    mgr = ContextWindowManager(max_tokens=100)
    context_lifecycle.register_session("sum-s")
    fp = ContextFingerprint(context_hash="a", token_utilization=0.95)
    assert context_lifecycle.should_summarize(fp)
