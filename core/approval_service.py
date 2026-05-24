"""Immutable approval workflow with policy re-validation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from core.policy import PolicyDecision, policy_engine
from core.persistence import persist_execution_bundle
from schemas.approvals import ActionProposal, Approval, ApprovalStatus, ImmutableActionProposal
from schemas.effects import SideEffectRecord
from tools.router import execute_tool


def proposal_checksum(proposal: ImmutableActionProposal) -> str:
    payload = proposal.model_dump(mode="json", exclude={"checksum"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def create_immutable_proposal(
    *,
    correlation_id: str,
    action: str,
    parameters: dict,
    agent: str,
    side_effect_level: str,
    impact_summary: str,
    proposed_by: str,
    approval_level: int,
    expires_at: datetime,
    task_id: str | None = None,
) -> ImmutableActionProposal:
    proposal = ImmutableActionProposal(
        id=str(uuid4()),
        correlation_id=correlation_id,
        task_id=task_id or correlation_id,
        agent=agent,
        action=action,
        parameters=parameters,
        side_effect_level=side_effect_level,
        impact_summary=impact_summary,
        proposed_by=proposed_by,
        approval_level=approval_level,
        expires_at=expires_at,
        checksum="",
    )
    proposal.checksum = proposal_checksum(proposal)
    return proposal


async def prepare_approval(proposal: ImmutableActionProposal, requester_agent: str) -> Approval:
    if proposal.checksum != proposal_checksum(proposal):
        raise ValueError("Proposal checksum invalid")
    action_proposal = ActionProposal(
        task_id=proposal.task_id,
        agent=proposal.agent,
        action=proposal.action,
        side_effect_level=proposal.side_effect_level,
        impact_summary=proposal.impact_summary,
    )
    decision = policy_engine.evaluate(action_proposal)
    if decision == PolicyDecision.DENY:
        raise ValueError("Policy denied action")
    approval = Approval(
        id=str(uuid4()),
        task_id=proposal.task_id,
        proposal=action_proposal,
        immutable_proposal=proposal,
        requester_agent=requester_agent,
        risk_level=proposal.approval_level,
        correlation_id=proposal.correlation_id,
        expires_at=proposal.expires_at,
    )
    policy_engine.register_approval(approval)
    return approval


async def execute_approved_action(approval: Approval, approved_by: str) -> dict:
    frozen = approval.immutable_proposal
    if frozen is None:
        raise ValueError("Missing immutable proposal")
    if frozen.checksum != proposal_checksum(frozen):
        raise ValueError("Checksum mismatch — proposal tampered")
    now = datetime.now(timezone.utc)
    expires = frozen.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        approval.status = ApprovalStatus.EXPIRED
        raise ValueError("Approval expired")

    action_proposal = ActionProposal(
        task_id=frozen.task_id,
        agent=frozen.agent,
        action=frozen.action,
        side_effect_level=frozen.side_effect_level,
        impact_summary=frozen.impact_summary,
    )
    decision = policy_engine.evaluate(action_proposal)
    if decision != PolicyDecision.ALLOW and decision != PolicyDecision.ESCALATE:
        raise ValueError(f"Policy re-validation failed: {decision.value}")
    if decision == PolicyDecision.ESCALATE and frozen.approval_level < 2:
        raise ValueError("Policy requires approval but level insufficient")

    result = await execute_tool(
        frozen.action,
        frozen.agent,
        frozen.correlation_id,
        frozen.parameters,
        skip_policy=False,
    )

    effect = SideEffectRecord(
        id=str(uuid4()),
        action_id=frozen.id,
        correlation_id=frozen.correlation_id,
        systems_affected=[frozen.action],
        mutation_status="complete" if result.success else "failed",
        rollback_available=False,
        created_at=datetime.now(timezone.utc),
    )
    await persist_execution_bundle(
        correlation_id=frozen.correlation_id,
        event_type="approval.executed",
        event_payload={
            "approval_id": approval.id,
            "approved_by": approved_by,
            "action": frozen.action,
            "success": result.success,
        },
        side_effect=effect,
    )
    return {"approval_id": approval.id, "execution": result.model_dump(), "side_effect": effect.model_dump()}
