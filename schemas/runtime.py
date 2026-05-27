from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RuntimeState(str, Enum):
    IDLE = "idle"
    PERCEIVING = "perceiving"
    REASONING = "reasoning"
    WAITING_TOOL = "waiting_tool"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REPLANNING = "replanning"
    ESCALATED = "escalated"
    FAILED = "failed"
    COMPLETED = "completed"


VALID_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.IDLE: {RuntimeState.PERCEIVING},
    RuntimeState.PERCEIVING: {
        RuntimeState.REASONING,
        RuntimeState.WAITING_TOOL,
        RuntimeState.ESCALATED,
        RuntimeState.FAILED,
    },
    RuntimeState.REASONING: {
        RuntimeState.WAITING_TOOL,
        RuntimeState.WAITING_APPROVAL,
        RuntimeState.EXECUTING,
        RuntimeState.REPLANNING,
        RuntimeState.FAILED,
        RuntimeState.COMPLETED,
    },
    RuntimeState.WAITING_TOOL: {RuntimeState.OBSERVING, RuntimeState.FAILED, RuntimeState.REPLANNING},
    RuntimeState.WAITING_APPROVAL: {RuntimeState.EXECUTING, RuntimeState.FAILED, RuntimeState.ESCALATED},
    RuntimeState.EXECUTING: {RuntimeState.OBSERVING, RuntimeState.FAILED, RuntimeState.COMPLETED},
    RuntimeState.OBSERVING: {
        RuntimeState.REASONING,
        RuntimeState.REPLANNING,
        RuntimeState.COMPLETED,
        RuntimeState.FAILED,
    },
    RuntimeState.REPLANNING: {RuntimeState.REASONING, RuntimeState.ESCALATED, RuntimeState.FAILED},
    RuntimeState.ESCALATED: {RuntimeState.REASONING, RuntimeState.FAILED, RuntimeState.COMPLETED},
    RuntimeState.FAILED: set(),
    RuntimeState.COMPLETED: set(),
}


class ContextLayer(str, Enum):
    L1_ACTIVE_TASK = "l1"
    L2_WORLD_STATE = "l2"
    L3_RECENT_DECISIONS = "l3"
    L4_LONG_TERM = "l4"
    L5_ARCHIVED = "l5"


class RetryPolicy(BaseModel):
    max_retries: int = 2
    retry_backoff_ms: int = 500
    retry_on: list[str] = ["timeout", "503", "connection_error"]
    escalation_after: int = 2


class CognitiveBudget(BaseModel):
    reasoning_budget: int = 4000
    planning_budget: int = 2000
    tool_budget: int = 5
    memory_budget: int = 8000
    debate_budget: int = 0
    max_cost_usd: float = 1.0
    fallback_model: str = "gpt-4o-mini"
    max_retries: int = 3
    force_deterministic: bool = False


class OutboxEvent(BaseModel):
    id: str
    idempotency_key: str
    correlation_id: str
    causation_id: str | None = None
    event_type: str
    payload: dict
    world_state_version: int
    processed: bool = False
    created_at: datetime


class ReplayMode(str, Enum):
    FROZEN = "frozen"
    LIVE = "live"


class ReplaySnapshot(BaseModel):
    step: int
    runtime_state: RuntimeState
    prompt_hash: str
    tool_outputs: dict[str, dict]
    world_state_version: int
    timestamp: datetime


class ReplaySession(BaseModel):
    session_id: str
    correlation_id: str
    mode: ReplayMode
    world_state_snapshot: dict  # serialized WorldStateSnapshot
    snapshots: list[ReplaySnapshot] = Field(default_factory=list)
    outcome_match: bool | None = None
