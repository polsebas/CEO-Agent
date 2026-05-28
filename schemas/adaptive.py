"""RRM-3 adaptive cognition schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from schemas.runtime_health import HealthBand


class AdaptivePolicy(BaseModel):
    max_retry_depth: int = 3
    context_budget_ratio: float = 1.0
    delegation_enabled: bool = True
    deterministic_mode: bool = False
    tool_parallelism_limit: int = 3
    approval_escalation_bias: float = 0.0


class AdaptiveSignals(BaseModel):
    """Deterministic inputs for policy derivation."""

    correlation_id: str
    session_id: str
    retry_density: float = 0.0
    replay_confidence: float = 1.0
    drift_severity: float = 0.0
    context_pressure: float = 0.0
    tool_failure_rate: float = 0.0
    health_band: HealthBand = HealthBand.HEALTHY
    degraded_mode_active: bool = False
    session_age_seconds: int = 0
    latency_pressure: float = 0.0
    stability_pressure: float = 0.0
    governance_pressure: float = 0.0


class AdaptivePolicySnapshot(BaseModel):
    session_id: str
    correlation_id: str
    policy: AdaptivePolicy
    signals_hash: str
    policy_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
