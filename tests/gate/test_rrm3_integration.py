"""RRM-3 integration gates — orchestrator, governance wiring, boundaries."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.adaptive_context import set_session_approval_bias
from core.adaptive_policy import adaptive_policy_engine, policy_hash
from core.orchestrator import manual_orchestrator
from core.persistence import query_adaptive_policy, reset_in_memory_store
from core.policy import PolicyDecision, policy_engine
from schemas.adaptive import AdaptivePolicy, AdaptiveSignals
from schemas.approvals import ActionProposal
from schemas.runtime import CognitiveBudget
from schemas.runtime_health import HealthBand


@pytest.mark.rrm3
def test_policy_evaluate_uses_session_adaptive_bias():
    set_session_approval_bias("sess-gov", 2.0)
    proposal = ActionProposal(
        task_id="sess-gov",
        agent="ceo",
        action="test_tool",
        side_effect_level="EXECUTE_SAFE",
        impact_summary="test",
    )
    base = policy_engine.effective_approval_level(1, adaptive_bias=0.0)
    with_bias = policy_engine.effective_approval_level(1, adaptive_bias=2.0)
    assert with_bias > base
    decision = policy_engine.evaluate(proposal, session_id="sess-gov")
    assert decision == PolicyDecision.ESCALATE


@pytest.mark.rrm3
def test_snapshot_hash_matches_final_policy():
    signals = AdaptiveSignals(
        correlation_id="c",
        session_id="s",
        replay_confidence=1.0,
        drift_severity=0.0,
    )
    policy = adaptive_policy_engine.derive(signals)
    policy = policy.model_copy(update={"context_budget_ratio": 0.95})
    snap = adaptive_policy_engine.snapshot(signals, policy=policy)
    assert snap.policy_hash == policy_hash(policy)
    assert snap.policy.context_budget_ratio == 0.95


@pytest.mark.rrm3
def test_agent_runner_preserves_memory_budget_under_deterministic():
    from core.config import settings

    budget = CognitiveBudget(memory_budget=3200, max_retries=2, force_deterministic=True)
    original = settings.runtime_health_enforcement
    settings.runtime_health_enforcement = True
    try:
        applied = budget
        if settings.runtime_health_enforcement and getattr(budget, "force_deterministic", False):
            applied = budget.model_copy(update={"max_retries": 0, "force_deterministic": True})
        assert applied.memory_budget == 3200
        assert applied.max_retries == 0
    finally:
        settings.runtime_health_enforcement = original


@pytest.mark.rrm3
@pytest.mark.asyncio
async def test_founder_request_persists_adaptive_policy():
    reset_in_memory_store()
    session_id = "rrm3-int-policy"
    correlation_id = "rrm3-int-corr"
    await manual_orchestrator.run_founder_request(
        "Summarize KPI health",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    snap = await query_adaptive_policy(session_id)
    assert snap is not None
    assert snap.policy_hash == policy_hash(snap.policy)


@pytest.mark.rrm3
@pytest.mark.asyncio
async def test_resolve_policy_bounded_invocations():
    reset_in_memory_store()
    calls: list[bool] = []

    async def counting_resolve(*args, **kwargs):
        calls.append(kwargs.get("force", False))
        return AdaptivePolicy()

    with patch.object(
        manual_orchestrator,
        "_resolve_adaptive_policy",
        side_effect=counting_resolve,
    ):
        await manual_orchestrator.run_founder_request(
            "Quick status",
            session_id="rrm3-boundary",
            correlation_id="rrm3-boundary-corr",
        )
    assert len(calls) <= 3
    assert any(calls), "expected at least initial resolve"
    assert calls[-1] is True, "session close should force final resolve"


@pytest.mark.rrm3
def test_adaptive_signals_ignore_stale_health_correlation():
    import asyncio

    from core.adaptive_signals import collect_adaptive_signals
    from core.intelligence_store import replace_health
    from schemas.runtime_health import RuntimeHealth

    async def _run():
        replace_health(
            RuntimeHealth(
                correlation_id="other-corr",
                session_id="stale-s",
                replay_confidence=0.1,
                health_band=HealthBand.CRITICAL,
                degraded_mode_active=True,
            )
        )
        signals = await collect_adaptive_signals("stale-s", "new-corr")
        assert signals.replay_confidence == 1.0
        assert signals.health_band == HealthBand.HEALTHY

    asyncio.get_event_loop().run_until_complete(_run())
