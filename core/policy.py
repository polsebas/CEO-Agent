"""Policy engine with crisis mode overrides."""

from __future__ import annotations

from enum import Enum
from typing import Any

from schemas.approvals import ActionProposal, Approval, ApprovalStatus
from schemas.crisis import CRISIS_OVERRIDES, CrisisType
from schemas.world import WorldState


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


SIDE_EFFECT_LEVELS = {
    "READ": 0,
    "PLAN": 1,
    "EXECUTE_SAFE": 2,
    "EXECUTE_CRITICAL": 3,
}


class PolicyEngine:
    def __init__(self) -> None:
        self.active_crisis: CrisisType | None = None

    def detect_crisis(self, world_state: WorldState) -> CrisisType | None:
        for incident in world_state.active_incidents:
            if incident.severity == "critical" and incident.status != "resolved":
                return CrisisType.INFRASTRUCTURE
        if world_state.company.runway_months < 3:
            return CrisisType.FINANCIAL
        return None

    def activate_crisis_if_needed(self, world_state: WorldState) -> CrisisType | None:
        crisis = self.detect_crisis(world_state)
        self.active_crisis = crisis
        return crisis

    def effective_approval_level(self, base_level: int, *, adaptive_bias: float = 0.0) -> int:
        """RRM-3: adaptive_bias may only escalate (non-negative)."""
        bias = max(0.0, adaptive_bias)
        if not self.active_crisis:
            return base_level + int(bias)
        override = CRISIS_OVERRIDES[self.active_crisis]
        adjusted = base_level + override.approval_level_delta + int(bias)
        return max(0, min(override.max_bypass_level, adjusted))

    def evaluate(
        self,
        proposal: ActionProposal,
        *,
        session_id: str | None = None,
        extra_approval_bias: float = 0.0,
    ) -> PolicyDecision:
        from core.adaptive_context import get_session_approval_bias

        level = SIDE_EFFECT_LEVELS.get(proposal.side_effect_level, 3)
        sid = session_id or proposal.task_id
        bias = get_session_approval_bias(sid) + max(0.0, extra_approval_bias)
        effective = self.effective_approval_level(level, adaptive_bias=bias)
        if effective <= 1:
            return PolicyDecision.ALLOW
        if effective >= 2:
            return PolicyDecision.ESCALATE
        return PolicyDecision.DENY

    async def get_approval(self, approval_id: str, *, conn: Any | None = None) -> Approval | None:
        from core.governance_store import load_approval
        from core.persistence import get_pool
        from core.runtime_session import MemoryConnection

        if conn is not None:
            return await load_approval(conn, approval_id)
        pool = await get_pool()
        if pool:
            async with pool.acquire() as c:
                return await load_approval(c, approval_id)
        from core.governance_store import _in_memory_approvals

        return _in_memory_approvals.get(approval_id)

    async def list_pending_approvals(self, *, conn: Any | None = None) -> list[Approval]:
        from core.governance_store import list_pending_approvals

        return await list_pending_approvals(conn)

    async def approve(self, conn: Any, approval_id: str, approved_by: str) -> Approval | None:
        from core.governance_store import load_approval, update_approval_status

        approval = await load_approval(conn, approval_id)
        if not approval or approval.status != ApprovalStatus.PENDING:
            return None
        return await update_approval_status(conn, approval_id, ApprovalStatus.APPROVED, approved_by=approved_by)


policy_engine = PolicyEngine()
