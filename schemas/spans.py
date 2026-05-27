"""Execution span models for RRM-2 observability."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SpanType(str, Enum):
    ORCHESTRATION = "orchestration"
    TRANSITION = "transition"
    TOOL_EXECUTION = "tool_execution"
    CONTEXT_BUILD = "context_build"
    AGENT_REASONING = "agent_reasoning"
    APPROVAL = "approval"
    REPLAY = "replay"
    RETRY = "retry"


class SpanStatus(str, Enum):
    STARTED = "started"
    OK = "ok"
    ERROR = "error"


class ExecutionSpan(BaseModel):
    span_id: str
    trace_id: str
    correlation_id: str
    session_id: str
    parent_span_id: str | None = None
    span_type: SpanType
    runtime_state: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: SpanStatus = SpanStatus.STARTED
    metadata: dict[str, Any] = Field(default_factory=dict)
