"""Runtime health and anomaly models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthBand(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuntimeHealth(BaseModel):
    correlation_id: str
    session_id: str
    orchestration_health: float = 1.0
    cognition_stability: float = 1.0
    replay_confidence: float = 1.0
    context_pressure: float = 0.0
    retry_pressure: float = 0.0
    tool_failure_rate: float = 0.0
    health_band: HealthBand = HealthBand.HEALTHY
    degraded_mode_active: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeAnomaly(BaseModel):
    anomaly_type: str
    severity: AnomalySeverity
    correlation_id: str
    session_id: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    related_span_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
