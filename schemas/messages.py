from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    CEO = "ceo"
    CFO = "cfo"
    COO = "coo"
    CTO = "cto"
    CMO = "cmo"


class MessageIntent(str, Enum):
    DELEGATION = "delegation"
    REPORT = "report"
    ESCALATION = "escalation"


class AgentMessage(BaseModel):
    id: str
    sender: AgentRole
    receiver: AgentRole | Literal["human"]
    intent: MessageIntent
    payload: dict
    context_refs: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    correlation_id: str
    causation_id: str | None = None
