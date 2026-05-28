"""RRM-3E — replay-aware governance gates."""

from __future__ import annotations

import pytest

from core.adaptive_governance import adaptive_governance_service
from core.adaptive_policy import adaptive_policy_engine
from core.policy import PolicyDecision, policy_engine
from schemas.approvals import ActionProposal
from core.replay_policy import replay_cognition_relaxation, replay_governance_pressure
from schemas.adaptive import AdaptivePolicy, AdaptiveSignals
from schemas.diagnostics import ReplayAnalytics


@pytest.mark.rrm3
def test_drift_escalates_governance():
    analytics = ReplayAnalytics(
        session_id="s",
        correlation_id="c",
        replay_confidence=0.2,
        drift_severity=0.9,
        outcome_match=False,
    )
    assert replay_governance_pressure(analytics) >= 0.5
    events = adaptive_governance_service.events_from_analytics(analytics)
    assert len(events) >= 1


@pytest.mark.rrm3
def test_stable_replay_no_governance_relaxation():
    analytics = ReplayAnalytics(
        session_id="s",
        correlation_id="c",
        replay_confidence=0.95,
        drift_severity=0.0,
        outcome_match=True,
    )
    base = policy_engine.effective_approval_level(2)
    with_bias = policy_engine.effective_approval_level(2, adaptive_bias=0.0)
    assert with_bias == base
    assert replay_governance_pressure(analytics) == 0.0


@pytest.mark.rrm3
def test_stable_replay_may_relax_cognition_only():
    analytics = ReplayAnalytics(
        session_id="s",
        correlation_id="c",
        replay_confidence=1.0,
        drift_severity=0.0,
        outcome_match=True,
    )
    policy = AdaptivePolicy(context_budget_ratio=0.8)
    relaxed = adaptive_governance_service.adjust_policy_cognition_only(policy, analytics)
    assert relaxed.context_budget_ratio >= policy.context_budget_ratio
    assert replay_cognition_relaxation(analytics) > 0


@pytest.mark.rrm3
def test_high_bias_escalates_tool_via_evaluate():
    from core.adaptive_context import set_session_approval_bias

    set_session_approval_bias("esc-s", 2.0)
    proposal = ActionProposal(
        task_id="esc-s",
        agent="ceo",
        action="deploy",
        side_effect_level="EXECUTE_SAFE",
        impact_summary="deploy",
    )
    assert policy_engine.evaluate(proposal, session_id="esc-s") == PolicyDecision.ESCALATE


@pytest.mark.rrm3
def test_approval_bias_never_negative():
    signals = AdaptiveSignals(correlation_id="c", session_id="s", governance_pressure=0.8)
    policy = adaptive_policy_engine.derive(signals)
    delta = adaptive_governance_service.effective_approval_delta(policy)
    assert delta >= 0
