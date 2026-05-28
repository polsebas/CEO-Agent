"""RRM-3B — tool reliability gates."""

from __future__ import annotations

import pytest

from core.tool_reliability import apply_hysteresis, compute_confidence_score, tool_reliability_service
from schemas.tools import ToolReliabilityProfile, ToolResult, ToolRoutingBand


@pytest.mark.rrm3
def test_confidence_reproducible():
    a = compute_confidence_score(
        success_rate=0.8,
        timeout_rate=0.1,
        replay_stability=0.9,
        drift_rate=0.05,
        average_latency_ms=200,
    )
    b = compute_confidence_score(
        success_rate=0.8,
        timeout_rate=0.1,
        replay_stability=0.9,
        drift_rate=0.05,
        average_latency_ms=200,
    )
    assert a == b


@pytest.mark.rrm3
def test_hysteresis_no_flap():
    profile = ToolReliabilityProfile(
        tool_name="t",
        confidence_score=0.75,
        routing_band=ToolRoutingBand.TRUSTED,
    )
    profile.routing_band = apply_hysteresis(profile)
    assert profile.routing_band == ToolRoutingBand.TRUSTED

    profile.confidence_score = 0.65
    profile.routing_band = apply_hysteresis(profile)
    assert profile.routing_band == ToolRoutingBand.DEGRADED

    profile.confidence_score = 0.79
    profile.routing_band = ToolRoutingBand.DEGRADED
    profile.routing_band = apply_hysteresis(profile)
    assert profile.routing_band == ToolRoutingBand.DEGRADED

    profile.confidence_score = 0.85
    profile.routing_band = apply_hysteresis(profile)
    assert profile.routing_band == ToolRoutingBand.TRUSTED


@pytest.mark.rrm3
def test_timeout_penalty():
    good = compute_confidence_score(
        success_rate=1.0,
        timeout_rate=0.0,
        replay_stability=1.0,
        drift_rate=0.0,
        average_latency_ms=100,
    )
    bad = compute_confidence_score(
        success_rate=1.0,
        timeout_rate=0.5,
        replay_stability=1.0,
        drift_rate=0.0,
        average_latency_ms=100,
    )
    assert bad < good


@pytest.mark.rrm3
def test_update_from_result():
    result = ToolResult(
        success=False,
        errors=["timeout"],
        source="test",
        latency_ms=5000,
        tool_name="get_repo_health",
        correlation_id="c",
    )
    profile = tool_reliability_service.update_from_result(None, result)
    assert profile.sample_count == 1
    assert profile.confidence_score < 1.0
