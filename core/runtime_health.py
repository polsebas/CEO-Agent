"""Deterministic runtime health engine."""

from __future__ import annotations

from schemas.cognition import CognitiveTelemetry
from schemas.runtime_health import AnomalySeverity, HealthBand, RuntimeAnomaly, RuntimeHealth
from schemas.spans import ExecutionSpan, SpanStatus


def _band(score: float) -> HealthBand:
    if score >= 0.9:
        return HealthBand.HEALTHY
    if score >= 0.7:
        return HealthBand.WARNING
    if score >= 0.4:
        return HealthBand.DEGRADED
    return HealthBand.CRITICAL


class RuntimeHealthEngine:
    def compute(
        self,
        *,
        correlation_id: str,
        session_id: str,
        telemetry: list[CognitiveTelemetry],
        spans: list[ExecutionSpan],
        tool_failure_rate: float = 0.0,
        replay_confidence: float = 1.0,
        context_pressure: float = 0.0,
    ) -> RuntimeHealth:
        retry_pressure = 0.0
        if telemetry:
            retry_pressure = min(1.0, sum(t.retry_count for t in telemetry) / (len(telemetry) * 3))

        error_spans = sum(1 for s in spans if s.status == SpanStatus.ERROR)
        span_penalty = min(0.5, error_spans / max(len(spans), 1))

        cognition_stability = max(0.0, 1.0 - retry_pressure - span_penalty)
        orchestration_health = max(0.0, 1.0 - tool_failure_rate - span_penalty * 0.5)
        composite = (
            orchestration_health * 0.3
            + cognition_stability * 0.25
            + replay_confidence * 0.2
            + max(0.0, 1.0 - context_pressure) * 0.15
            + max(0.0, 1.0 - retry_pressure) * 0.1
        )
        band = _band(composite)
        return RuntimeHealth(
            correlation_id=correlation_id,
            session_id=session_id,
            orchestration_health=round(orchestration_health, 4),
            cognition_stability=round(cognition_stability, 4),
            replay_confidence=round(replay_confidence, 4),
            context_pressure=round(context_pressure, 4),
            retry_pressure=round(retry_pressure, 4),
            tool_failure_rate=round(tool_failure_rate, 4),
            health_band=band,
            degraded_mode_active=band in (HealthBand.DEGRADED, HealthBand.CRITICAL),
        )

    def detect_anomalies(
        self,
        health: RuntimeHealth,
        *,
        spans: list[ExecutionSpan],
    ) -> list[RuntimeAnomaly]:
        anomalies: list[RuntimeAnomaly] = []
        if health.retry_pressure > 0.6:
            anomalies.append(
                RuntimeAnomaly(
                    anomaly_type="excessive_retries",
                    severity=AnomalySeverity.HIGH,
                    correlation_id=health.correlation_id,
                    session_id=health.session_id,
                    metadata={"retry_pressure": health.retry_pressure},
                )
            )
        if health.context_pressure > 0.9:
            anomalies.append(
                RuntimeAnomaly(
                    anomaly_type="context_overflow",
                    severity=AnomalySeverity.MEDIUM,
                    correlation_id=health.correlation_id,
                    session_id=health.session_id,
                    metadata={"context_pressure": health.context_pressure},
                )
            )
        if health.replay_confidence < 0.5:
            anomalies.append(
                RuntimeAnomaly(
                    anomaly_type="replay_divergence",
                    severity=AnomalySeverity.HIGH,
                    correlation_id=health.correlation_id,
                    session_id=health.session_id,
                    metadata={"replay_confidence": health.replay_confidence},
                )
            )
        if health.tool_failure_rate > 0.5:
            anomalies.append(
                RuntimeAnomaly(
                    anomaly_type="repeated_tool_failure",
                    severity=AnomalySeverity.HIGH,
                    correlation_id=health.correlation_id,
                    session_id=health.session_id,
                    metadata={"tool_failure_rate": health.tool_failure_rate},
                )
            )
        if health.health_band == HealthBand.CRITICAL:
            anomalies.append(
                RuntimeAnomaly(
                    anomaly_type="degraded_cognition",
                    severity=AnomalySeverity.CRITICAL,
                    correlation_id=health.correlation_id,
                    session_id=health.session_id,
                )
            )
        return anomalies


runtime_health_engine = RuntimeHealthEngine()
