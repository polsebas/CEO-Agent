from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"


class Task(BaseModel):
    id: str
    objective: str
    owner_agent: str
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = TaskStatus.CREATED
    approval_level: Literal[0, 1, 2, 3, 4] = 0
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    dependencies: list[str] = Field(default_factory=list)
    correlation_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActionProposal(BaseModel):
    task_id: str
    agent: str
    action: str
    side_effect_level: Literal["READ", "PLAN", "EXECUTE_SAFE", "EXECUTE_CRITICAL"]
    impact_summary: str
    rollback_strategy: str | None = None
    estimated_cost_usd: float = 0.0


class ImmutableActionProposal(BaseModel):
    id: str
    correlation_id: str
    task_id: str
    agent: str
    action: str
    parameters: dict = Field(default_factory=dict)
    side_effect_level: Literal["READ", "PLAN", "EXECUTE_SAFE", "EXECUTE_CRITICAL"]
    impact_summary: str
    proposed_by: str
    approval_level: int = Field(ge=0, le=4)
    checksum: str
    expires_at: datetime


class Approval(BaseModel):
    id: str
    task_id: str
    proposal: ActionProposal
    requester_agent: str
    risk_level: int
    status: ApprovalStatus = ApprovalStatus.PENDING
    correlation_id: str
    expires_at: datetime
    immutable_proposal: ImmutableActionProposal | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
