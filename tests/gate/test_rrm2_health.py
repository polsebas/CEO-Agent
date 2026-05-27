"""RRM-2C — runtime health gate."""

from __future__ import annotations

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import query_runtime_health, reset_in_memory_store
from core.runtime_health import runtime_health_engine
from schemas.cognition import CognitiveTelemetry
from schemas.runtime_health import HealthBand


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_health_snapshot_on_session_complete():
    reset_in_memory_store()
    session_id = "rrm2-health"
    correlation_id = "rrm2-health-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    rows = await query_runtime_health(session_id)
    assert len(rows) >= 1
    assert rows[-1].health_band in HealthBand


@pytest.mark.rrm2
def test_health_deterministic_same_inputs():
    tel = [
        CognitiveTelemetry(
            correlation_id="c",
            session_id="s",
            agent_id="ceo",
            retry_count=2,
            context_pressure=0.5,
            token_estimate=100,
        )
    ]
    h1 = runtime_health_engine.compute(
        correlation_id="c",
        session_id="s",
        telemetry=tel,
        spans=[],
        tool_failure_rate=0.1,
        replay_confidence=1.0,
        context_pressure=0.5,
    )
    h2 = runtime_health_engine.compute(
        correlation_id="c",
        session_id="s",
        telemetry=tel,
        spans=[],
        tool_failure_rate=0.1,
        replay_confidence=1.0,
        context_pressure=0.5,
    )
    assert h1.health_band == h2.health_band
    assert h1.degraded_mode_active == h2.degraded_mode_active


@pytest.mark.rrm2
def test_degraded_mode_on_critical_pressure():
    tel = [
        CognitiveTelemetry(
            correlation_id="c",
            session_id="s",
            agent_id="ceo",
            retry_count=10,
            context_pressure=0.95,
            token_estimate=9000,
        )
    ]
    h = runtime_health_engine.compute(
        correlation_id="c",
        session_id="s",
        telemetry=tel,
        spans=[],
        tool_failure_rate=0.8,
        replay_confidence=0.2,
        context_pressure=0.95,
    )
    anomalies = runtime_health_engine.detect_anomalies(h, spans=[])
    assert h.degraded_mode_active or h.health_band in (HealthBand.DEGRADED, HealthBand.CRITICAL)
    assert any(a.anomaly_type == "context_overflow" for a in anomalies)
