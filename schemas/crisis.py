from enum import Enum

from pydantic import BaseModel, Field

from schemas.runtime import ContextLayer


class CrisisType(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    FINANCIAL = "financial"
    SECURITY = "security"
    CUSTOMER = "customer"
    COMPLIANCE = "compliance"


class CrisisOverride(BaseModel):
    crisis_type: CrisisType
    budget_multiplier: float = 2.0
    approval_level_delta: int = -1
    routing_priority: list[str] = Field(default_factory=list)
    context_expansion: list[ContextLayer] = Field(default_factory=list)
    max_bypass_level: int = 2


CRISIS_OVERRIDES: dict[CrisisType, CrisisOverride] = {
    CrisisType.INFRASTRUCTURE: CrisisOverride(
        crisis_type=CrisisType.INFRASTRUCTURE,
        budget_multiplier=2.0,
        approval_level_delta=-1,
        routing_priority=["cto", "coo"],
        context_expansion=[ContextLayer.L3_RECENT_DECISIONS],
    ),
    CrisisType.FINANCIAL: CrisisOverride(
        crisis_type=CrisisType.FINANCIAL,
        budget_multiplier=1.5,
        approval_level_delta=0,
        routing_priority=["cfo", "ceo"],
        context_expansion=[ContextLayer.L3_RECENT_DECISIONS],
    ),
    CrisisType.SECURITY: CrisisOverride(
        crisis_type=CrisisType.SECURITY,
        budget_multiplier=2.0,
        approval_level_delta=0,
        routing_priority=["cto", "ceo"],
        context_expansion=[ContextLayer.L3_RECENT_DECISIONS, ContextLayer.L4_LONG_TERM],
    ),
    CrisisType.CUSTOMER: CrisisOverride(
        crisis_type=CrisisType.CUSTOMER,
        budget_multiplier=1.5,
        approval_level_delta=0,
        routing_priority=["cmo", "coo"],
        context_expansion=[ContextLayer.L3_RECENT_DECISIONS],
    ),
    CrisisType.COMPLIANCE: CrisisOverride(
        crisis_type=CrisisType.COMPLIANCE,
        budget_multiplier=1.0,
        approval_level_delta=1,
        routing_priority=["ceo"],
        context_expansion=[ContextLayer.L4_LONG_TERM],
        max_bypass_level=1,
    ),
}
