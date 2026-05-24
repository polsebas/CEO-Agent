"""Policy engine with crisis mode overrides."""

from __future__ import annotations

from enum import Enum

from schemas.approvals import ActionProposal, Approval, ApprovalStatus
from schemas.crisis import CRISIS_OVERRIDES, CrisisType
from schemas.world import Incident, WorldState


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
        self._pending_approvals: dict[str, Approval] = {}

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

    def effective_approval_level(self, base_level: int) -> int:
        if not self.active_crisis:
            return base_level
        override = CRISIS_OVERRIDES[self.active_crisis]
        adjusted = base_level + override.approval_level_delta
        return max(0, min(override.max_bypass_level, adjusted))

    def evaluate(self, proposal: ActionProposal) -> PolicyDecision:
        level = SIDE_EFFECT_LEVELS.get(proposal.side_effect_level, 3)
        effective = self.effective_approval_level(level)
        if effective == 0:
            return PolicyDecision.ALLOW
        if effective == 1:
            return PolicyDecision.ALLOW
        if effective >= 2:
            return PolicyDecision.ESCALATE
        return PolicyDecision.DENY

    def register_approval(self, approval: Approval) -> None:
        self._pending_approvals[approval.id] = approval

    def get_approval(self, approval_id: str) -> Approval | None:
        return self._pending_approvals.get(approval_id)

    def list_pending_approvals(self) -> list[Approval]:
        return [a for a in self._pending_approvals.values() if a.status == ApprovalStatus.PENDING]

    def approve(self, approval_id: str, approved_by: str) -> Approval | None:
        from datetime import datetime

        approval = self._pending_approvals.get(approval_id)
        if not approval or approval.status != ApprovalStatus.PENDING:
            return None
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = approved_by
        approval.approved_at = datetime.utcnow()
        return approval

    def reject(self, approval_id: str) -> Approval | None:
        approval = self._pending_approvals.get(approval_id)
        if not approval:
            return None
        approval.status = ApprovalStatus.REJECTED
        return approval


policy_engine = PolicyEngine()
