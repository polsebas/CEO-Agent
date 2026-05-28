"""Unit tests for human session summaries."""

from __future__ import annotations

from schemas.diagnostics import ReplayAnalytics, SessionDiagnostics
from schemas.runtime_health import HealthBand, RuntimeHealth
from schemas.tools import ToolReliabilityProfile, ToolRoutingBand

from core.session_summary_builder import build_human_summaries


def test_degraded_mode_summary():
    diag = SessionDiagnostics(
        session_id="s1",
        correlation_id="c1",
        runtime_health=RuntimeHealth(
            correlation_id="c1",
            session_id="s1",
            degraded_mode_active=True,
            retry_pressure=0.8,
            health_band=HealthBand.DEGRADED,
            replay_confidence=0.6,
        ),
        telemetry_summary={"total_retries": 5},
    )
    lines = build_human_summaries(diag)
    assert any("degraded mode" in line.headline.lower() for line in lines)
    assert any(line.source == "degraded_mode" for line in lines)


def test_delegation_frozen_summary():
    diag = SessionDiagnostics(
        session_id="s1",
        correlation_id="c1",
        adaptive_policy_summary={"delegation_enabled": False},
    )
    lines = build_human_summaries(diag)
    assert any(line.source == "delegation_frozen" for line in lines)


def test_replay_drift_summary():
    diag = SessionDiagnostics(session_id="s1", correlation_id="c1")
    analytics = ReplayAnalytics(
        session_id="s1",
        correlation_id="c1",
        drift_severity=0.7,
        drift_fields=["tool_outputs"],
    )
    lines = build_human_summaries(diag, replay_analytics=analytics)
    assert any(line.source == "replay_drift" for line in lines)


def test_unstable_tool_summary():
    diag = SessionDiagnostics(session_id="s1", correlation_id="c1")
    tool = ToolReliabilityProfile(
        tool_name="github_deploy",
        success_rate=0.5,
        routing_band=ToolRoutingBand.DEGRADED,
    )
    lines = build_human_summaries(diag, unstable_tools=[tool])
    assert any("github_deploy" in line.headline for line in lines)
