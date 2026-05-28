from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ToolRoutingBand(str, Enum):
    TRUSTED = "trusted"
    DEGRADED = "degraded"


class ToolReliabilityProfile(BaseModel):
    tool_name: str
    success_rate: float = 1.0
    replay_stability: float = 1.0
    average_latency_ms: float = 0.0
    timeout_rate: float = 0.0
    drift_rate: float = 0.0
    confidence_score: float = 1.0
    routing_band: ToolRoutingBand = ToolRoutingBand.TRUSTED
    sample_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolResult(BaseModel):
    success: bool
    data: dict | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str
    latency_ms: int
    cached: bool = False
    tool_name: str
    correlation_id: str
