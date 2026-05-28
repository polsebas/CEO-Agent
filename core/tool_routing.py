"""Adaptive tool routing from reliability profiles."""

from __future__ import annotations

from dataclasses import dataclass

from schemas.adaptive import AdaptivePolicy
from schemas.tools import ToolReliabilityProfile, ToolRoutingBand


@dataclass
class ToolRoutingDecision:
    allow_parallel: bool
    require_approval_escalation: bool
    deterministic_fallback: bool
    skip_optional: bool


def decide_routing(
    profile: ToolReliabilityProfile | None,
    policy: AdaptivePolicy,
) -> ToolRoutingDecision:
    if profile is None:
        return ToolRoutingDecision(
            allow_parallel=policy.tool_parallelism_limit > 1,
            require_approval_escalation=False,
            deterministic_fallback=policy.deterministic_mode,
            skip_optional=False,
        )
    degraded_band = profile.routing_band == ToolRoutingBand.DEGRADED
    low_confidence = profile.confidence_score < settings_adaptive_low()
    return ToolRoutingDecision(
        allow_parallel=not degraded_band and policy.tool_parallelism_limit > 1,
        require_approval_escalation=degraded_band or low_confidence,
        deterministic_fallback=policy.deterministic_mode or degraded_band,
        skip_optional=degraded_band and profile.confidence_score < 0.5,
    )


def settings_adaptive_low() -> float:
    from core.config import settings

    return settings.adaptive_tool_enter_degraded
