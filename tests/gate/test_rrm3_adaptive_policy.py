"""RRM-3A — adaptive policy gates."""

from __future__ import annotations

import pytest

from core.adaptive_policy import adaptive_policy_engine, policy_hash, signals_hash
from schemas.adaptive import AdaptivePolicy, AdaptiveSignals
from schemas.runtime_health import HealthBand


@pytest.mark.rrm3
def test_same_signals_same_policy():
    signals = AdaptiveSignals(
        correlation_id="c1",
        session_id="s1",
        retry_density=0.7,
        context_pressure=0.9,
        replay_confidence=0.3,
        drift_severity=0.8,
        health_band=HealthBand.DEGRADED,
        degraded_mode_active=True,
    )
    p1 = adaptive_policy_engine.derive(signals)
    p2 = adaptive_policy_engine.derive(signals)
    assert policy_hash(p1) == policy_hash(p2)
    assert signals_hash(signals) == signals_hash(signals)


@pytest.mark.rrm3
def test_degraded_session_delegation_disabled():
    signals = AdaptiveSignals(
        correlation_id="c",
        session_id="s",
        health_band=HealthBand.CRITICAL,
        degraded_mode_active=True,
    )
    policy = adaptive_policy_engine.derive(signals)
    assert policy.delegation_enabled is False


@pytest.mark.rrm3
def test_replay_instability_deterministic_mode():
    signals = AdaptiveSignals(
        correlation_id="c",
        session_id="s",
        replay_confidence=0.2,
        drift_severity=0.9,
    )
    policy = adaptive_policy_engine.derive(signals)
    assert policy.deterministic_mode is True


@pytest.mark.rrm3
def test_context_pressure_reduces_budget():
    signals = AdaptiveSignals(
        correlation_id="c",
        session_id="s",
        context_pressure=0.95,
    )
    policy = adaptive_policy_engine.derive(signals)
    assert policy.context_budget_ratio < 1.0


@pytest.mark.rrm3
def test_retry_storm_lowers_retry_cap():
    signals = AdaptiveSignals(
        correlation_id="c",
        session_id="s",
        retry_density=0.9,
    )
    policy = adaptive_policy_engine.derive(signals)
    assert policy.max_retry_depth < 3
