"""Cognitive runtime telemetry."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StructuredRetryTrace(BaseModel):
    correlation_id: str
    session_id: str
    agent_id: str
    step_id: int
    validation_error: str | None = None
    repair_attempts: int = 0
    llm_retry_triggered: bool = False
    final_failure_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
