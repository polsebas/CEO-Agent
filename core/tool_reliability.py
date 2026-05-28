"""Tool reliability scoring with hysteresis anti-flapping."""

from __future__ import annotations

from datetime import datetime, timezone

from core.config import settings
from schemas.tools import ToolReliabilityProfile, ToolResult, ToolRoutingBand


def compute_confidence_score(
    *,
    success_rate: float,
    timeout_rate: float,
    replay_stability: float,
    drift_rate: float,
    average_latency_ms: float,
) -> float:
    latency_penalty = min(0.2, average_latency_ms / 10000.0)
    score = (
        success_rate * 0.35
        + replay_stability * 0.25
        + (1.0 - timeout_rate) * 0.2
        + (1.0 - drift_rate) * 0.15
        - latency_penalty
    )
    return round(max(0.0, min(1.0, score)), 4)


def apply_hysteresis(
    profile: ToolReliabilityProfile,
    *,
    enter_threshold: float | None = None,
    exit_threshold: float | None = None,
) -> ToolRoutingBand:
    enter = enter_threshold if enter_threshold is not None else settings.adaptive_tool_enter_degraded
    exit_th = exit_threshold if exit_threshold is not None else settings.adaptive_tool_exit_degraded
    score = profile.confidence_score
    if profile.routing_band == ToolRoutingBand.DEGRADED:
        if score >= exit_th:
            return ToolRoutingBand.TRUSTED
        return ToolRoutingBand.DEGRADED
    if score < enter:
        return ToolRoutingBand.DEGRADED
    return ToolRoutingBand.TRUSTED


class ToolReliabilityService:
    def update_from_result(
        self,
        profile: ToolReliabilityProfile | None,
        result: ToolResult,
        *,
        replay_stability: float = 1.0,
        drift_rate: float = 0.0,
    ) -> ToolReliabilityProfile:
        name = result.tool_name
        n = (profile.sample_count if profile else 0) + 1
        prev_success = profile.success_rate if profile else 1.0
        prev_timeout = profile.timeout_rate if profile else 0.0
        prev_latency = profile.average_latency_ms if profile else 0.0

        success = 1.0 if result.success else 0.0
        is_timeout = any("timeout" in e.lower() for e in result.errors)
        timeout = 1.0 if is_timeout else 0.0

        success_rate = ((prev_success * (n - 1)) + success) / n
        timeout_rate = ((prev_timeout * (n - 1)) + timeout) / n
        average_latency_ms = ((prev_latency * (n - 1)) + result.latency_ms) / n

        confidence = compute_confidence_score(
            success_rate=success_rate,
            timeout_rate=timeout_rate,
            replay_stability=replay_stability,
            drift_rate=drift_rate,
            average_latency_ms=average_latency_ms,
        )
        band = profile.routing_band if profile else ToolRoutingBand.TRUSTED
        updated = ToolReliabilityProfile(
            tool_name=name,
            success_rate=round(success_rate, 4),
            replay_stability=round(replay_stability, 4),
            average_latency_ms=round(average_latency_ms, 2),
            timeout_rate=round(timeout_rate, 4),
            drift_rate=round(drift_rate, 4),
            confidence_score=confidence,
            routing_band=band,
            sample_count=n,
            updated_at=datetime.now(timezone.utc),
        )
        updated.routing_band = apply_hysteresis(updated)
        return updated


tool_reliability_service = ToolReliabilityService()
