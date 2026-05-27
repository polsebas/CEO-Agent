"""Immutable approval workflow with policy re-validation and binding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.canonical import stable_hash
from core.governance_store import append_audit_event, load_approval, save_approval, update_approval_status
from core.persistence import get_world_state
from core.policy import PolicyDecision, policy_engine
from core.runtime_session import run_mutative_session
from core.spans import span_manager
from core.transaction import PersistRuntimePayload, persist_runtime_tx
from schemas.approvals import ActionProposal, Approval, ApprovalBinding, ApprovalStatus, ImmutableActionProposal
from schemas.spans import SpanStatus, SpanType
from schemas.effects import SideEffectRecord
from tools.router import execute_tool


def proposal_checksum(proposal: ImmutableActionProposal) -> str:
    return stable_hash(proposal.model_dump(mode="json", exclude={"checksum"}))


def build_approval_binding(proposal: ImmutableActionProposal, approval_id: str) -> ApprovalBinding:
    return ApprovalBinding(
        approval_id=approval_id,
        correlation_id=proposal.correlation_id,
        action_hash=stable_hash({"action": proposal.action, "agent": proposal.agent}),
        tool_name=proposal.action,
        parameters_hash=stable_hash(proposal.parameters),
        world_state_version=get_world_state().version,
        expires_at=proposal.expires_at,
        created_at=datetime.now(timezone.utc),
    )


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


async def prepare_approval(conn: Any, proposal: ImmutableActionProposal, requester_agent: str) -> Approval:
    span_manager.begin_session(
        session_id=proposal.correlation_id,
        correlation_id=proposal.correlation_id,
    )
    asp = span_manager.start(SpanType.APPROVAL, metadata={"phase": "prepare", "action": proposal.action})
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
    approval_id = str(uuid4())
    approval = Approval(
        id=approval_id,
        task_id=proposal.task_id,
        proposal=action_proposal,
        immutable_proposal=proposal,
        requester_agent=requester_agent,
        risk_level=proposal.approval_level,
        correlation_id=proposal.correlation_id,
        expires_at=proposal.expires_at,
        binding=build_approval_binding(proposal, approval_id),
    )
    await save_approval(conn, approval)
    await append_audit_event(
        conn,
        event_type="approval.prepared",
        actor=proposal.proposed_by,
        correlation_id=proposal.correlation_id,
        payload={"approval_id": approval_id, "action": proposal.action},
    )
    await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=proposal.correlation_id,
            session_id=proposal.correlation_id,
            event_type="approval.prepared",
            event_payload={"approval_id": approval_id, "action": proposal.action},
            business_key=f"approval:prepare:{approval_id}",
        ),
    )
    span_manager.end(asp, status=SpanStatus.OK)
    return approval


def _validate_binding(frozen: ImmutableActionProposal, approval: Approval) -> None:
    if approval.binding is None:
        raise ValueError("Missing approval binding")
    expected_action = stable_hash({"action": frozen.action, "agent": frozen.agent})
    if approval.binding.action_hash != expected_action:
        raise ValueError("Action hash mismatch — proposal tampered")
    if approval.binding.parameters_hash != stable_hash(frozen.parameters):
        raise ValueError("Parameters hash mismatch — proposal tampered")
    if approval.binding.tool_name != frozen.action:
        raise ValueError("Tool name mismatch in binding")


async def execute_approved_action(conn: Any, approval: Approval, approved_by: str) -> dict:
    span_manager.begin_session(
        session_id=approval.correlation_id,
        correlation_id=approval.correlation_id,
    )
    asp = span_manager.start(
        SpanType.APPROVAL,
        metadata={"phase": "execute", "approval_id": approval.id},
    )
    frozen = approval.immutable_proposal
    if frozen is None:
        raise ValueError("Missing immutable proposal")
    if frozen.checksum != proposal_checksum(frozen):
        raise ValueError("Checksum mismatch — proposal tampered")
    _validate_binding(frozen, approval)

    now = datetime.now(timezone.utc)
    expires = frozen.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        await update_approval_status(conn, approval.id, ApprovalStatus.EXPIRED)
        raise ValueError("Approval expired")

    action_proposal = ActionProposal(
        task_id=frozen.task_id,
        agent=frozen.agent,
        action=frozen.action,
        side_effect_level=frozen.side_effect_level,
        impact_summary=frozen.impact_summary,
    )
    decision = policy_engine.evaluate(action_proposal)
    if decision not in (PolicyDecision.ALLOW, PolicyDecision.ESCALATE):
        raise ValueError(f"Policy re-validation failed: {decision.value}")

    result = await execute_tool(
        frozen.action,
        frozen.agent,
        frozen.correlation_id,
        frozen.parameters,
        session_id=approval.correlation_id,
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
    sid = frozen.correlation_id
    await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=frozen.correlation_id,
            session_id=sid,
            event_type="approval.executed",
            event_payload={
                "approval_id": approval.id,
                "approved_by": approved_by,
                "action": frozen.action,
                "success": result.success,
            },
            side_effect=effect,
            business_key=f"approval:{approval.id}:executed",
        ),
    )
    await update_approval_status(conn, approval.id, ApprovalStatus.APPROVED, approved_by=approved_by)
    await append_audit_event(
        conn,
        event_type="approval.executed",
        actor=approved_by,
        correlation_id=frozen.correlation_id,
        payload={"approval_id": approval.id, "success": result.success},
    )
    span_manager.end(asp, status=SpanStatus.OK if result.success else SpanStatus.ERROR)
    return {"approval_id": approval.id, "execution": result.model_dump(), "side_effect": effect.model_dump()}


async def prepare_approval_in_session(proposal: ImmutableActionProposal, requester_agent: str) -> Approval:
    session_id = proposal.correlation_id

    async def _work(conn: Any) -> Approval:
        return await prepare_approval(conn, proposal, requester_agent)

    return await run_mutative_session(session_id, _work)


async def execute_approved_action_in_session(
    approval_id: str,
    approved_by: str,
    *,
    session_id: str | None = None,
) -> dict:
    sid = session_id or approval_id

    async def _work(conn: Any) -> dict:
        approval = await load_approval(conn, approval_id)
        if not approval or approval.status != ApprovalStatus.PENDING:
            raise ValueError("Approval not found or already processed")
        return await execute_approved_action(conn, approval, approved_by)

    return await run_mutative_session(sid, _work)
