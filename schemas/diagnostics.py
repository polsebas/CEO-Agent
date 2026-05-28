"""Session diagnostics and replay analytics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.runtime_health import RuntimeAnomaly, RuntimeHealth


class SessionDiagnostics(BaseModel):
    session_id: str
    correlation_id: str
    runtime_health: RuntimeHealth | None = None
    span_summary: dict[str, Any] = Field(default_factory=dict)
    telemetry_summary: dict[str, Any] = Field(default_factory=dict)
    replay_summary: dict[str, Any] = Field(default_factory=dict)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    anomaly_events: list[RuntimeAnomaly] = Field(default_factory=list)
    adaptive_policy_summary: dict[str, Any] = Field(default_factory=dict)
    stability_summary: dict[str, Any] = Field(default_factory=dict)
    governance_summary: dict[str, Any] = Field(default_factory=dict)


class ReplayAnalytics(BaseModel):
    session_id: str
    correlation_id: str
    replay_confidence: float = 1.0
    drift_severity: float = 0.0
    orchestration_version: str = ""
    context_divergence: float = 0.0
    tool_divergence: float = 0.0
    outcome_match: bool = True
    drift_fields: list[str] = Field(default_factory=list)
