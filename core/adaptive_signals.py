"""Aggregate deterministic runtime signals for policy derivation."""

from __future__ import annotations

from typing import Any

from core.config import settings
from core.context_lifecycle import context_lifecycle
from schemas.adaptive import AdaptiveSignals
from schemas.runtime_health import HealthBand, RuntimeHealth
from schemas.spans import ExecutionSpan, SpanStatus, SpanType


def _retry_density_from_telemetry(telemetry: list) -> float:
    if not telemetry:
        return 0.0
    total = sum(getattr(t, "retry_count", 0) for t in telemetry)
    return min(1.0, total / (len(telemetry) * 3))


def _latency_pressure(spans: list[ExecutionSpan]) -> float:
    cog = [s for s in spans if s.span_type == SpanType.AGENT_REASONING and s.completed_at]
    if not cog:
        return 0.0
    latencies = []
    for s in cog:
        if s.completed_at and s.started_at:
            ms = (s.completed_at - s.started_at).total_seconds() * 1000
            latencies.append(ms)
    if not latencies:
        return 0.0
    latencies.sort()
    p95_idx = min(len(latencies) - 1, int(len(latencies) * 0.95))
    p95 = latencies[p95_idx]
    return min(1.0, p95 / 30000.0)


async def collect_adaptive_signals(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
    health: RuntimeHealth | None = None,
    replay_confidence: float = 1.0,
    drift_severity: float = 0.0,
    context_pressure: float = 0.0,
    tool_failure_rate: float = 0.0,
    stability_pressure: float = 0.0,
    governance_pressure: float = 0.0,
) -> AdaptiveSignals:
    from core.persistence import query_cognitive_telemetry, query_execution_spans, query_runtime_health

    if health is None:
        rows = await query_runtime_health(session_id, conn=conn)
        health = rows[-1] if rows else None

    telemetry = await query_cognitive_telemetry(session_id, correlation_id=correlation_id, conn=conn)
    spans = await query_execution_spans(session_id, correlation_id=correlation_id, conn=conn)

    retry_density = _retry_density_from_telemetry(telemetry)
    if health and health.correlation_id == correlation_id:
        retry_density = max(retry_density, health.retry_pressure)
        context_pressure = max(context_pressure, health.context_pressure)
        if replay_confidence == 1.0 and drift_severity == 0.0:
            replay_confidence = health.replay_confidence
        tool_failure_rate = max(tool_failure_rate, health.tool_failure_rate)

    if telemetry and context_pressure == 0.0:
        context_pressure = telemetry[-1].context_pressure

    if health and health.correlation_id == correlation_id:
        band = health.health_band
        degraded = health.degraded_mode_active
    else:
        band = HealthBand.HEALTHY
        degraded = False

    return AdaptiveSignals(
        correlation_id=correlation_id,
        session_id=session_id,
        retry_density=round(retry_density, 4),
        replay_confidence=round(replay_confidence, 4),
        drift_severity=round(drift_severity, 4),
        context_pressure=round(context_pressure, 4),
        tool_failure_rate=round(tool_failure_rate, 4),
        health_band=band,
        degraded_mode_active=degraded,
        session_age_seconds=context_lifecycle.context_age_seconds(session_id),
        latency_pressure=round(_latency_pressure(spans), 4),
        stability_pressure=round(stability_pressure, 4),
        governance_pressure=round(governance_pressure, 4),
    )
