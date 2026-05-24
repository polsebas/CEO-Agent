from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.runtime import RuntimeState


class CalibratedConfidence(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)


class DecisionRecord(BaseModel):
    id: str
    correlation_id: str
    causation_id: str | None = None
    objective: str
    context_used: list[str] = Field(default_factory=list)
    policies_applied: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    reasoning_summary: str
    confidence: CalibratedConfidence
    final_action: str
    outcome: Literal["success", "failed", "pending", "rolled_back"] | None = None
    agent: str
    runtime_state: RuntimeState
    created_at: datetime
