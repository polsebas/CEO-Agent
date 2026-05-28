"""Session list and human-readable summary schemas for MVP UI."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    session_id: str
    correlation_id: str
    founder_request: str | None = None
    runtime_state: str = "unknown"
    health_status: str = "healthy"
    degraded: bool = False
    replay_confidence: float = 1.0
    pending_approvals: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionListFilters(BaseModel):
    limit: int = 50
    offset: int = 0
    status: str | None = None
    health: str | None = None
    has_pending_approvals: bool | None = None
    search: str | None = None
    degraded_only: bool = False


class HumanSummaryLine(BaseModel):
    severity: str  # info | warning | critical
    headline: str
    detail: str | None = None
    source: str  # retry_storm, replay_drift, tool_unstable, etc.
