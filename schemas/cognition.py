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


class CognitiveTelemetry(BaseModel):
    correlation_id: str
    session_id: str
    agent_id: str
    reasoning_latency_ms: int = 0
    retry_count: int = 0
    token_estimate: int = 0
    context_pressure: float = 0.0
    replay_confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PromptLineage(BaseModel):
    prompt_hash: str
    session_id: str
    correlation_id: str
    parent_prompt_hash: str | None = None
    derived_from_context_hash: str | None = None
    compression_strategy: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
