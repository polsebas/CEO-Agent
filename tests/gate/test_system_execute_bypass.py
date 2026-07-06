"""Gate: post-approval execution via agent_id=system bypasses policy escalation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.approval_service import create_immutable_proposal, execute_approved_action, prepare_approval
from core.persistence import reset_in_memory_store
from core.runtime_session import run_mutative_session
from schemas.approvals import ApprovalStatus
from tools.registry import ToolCapability, tool_registry
from tools.router import TOOL_HANDLERS, execute_tool


async def _noop_critical(**kwargs):
    return {"ok": True, **kwargs}


async def _failing_critical(**kwargs):
    raise RuntimeError("execution failed")


@pytest.fixture
def critical_test_tool(monkeypatch):
    name = "test_critical_side_effect"
    tool_registry.register(
        ToolCapability(
            name=name,
            action_class="EXECUTE",
            allowed_agents=["ceo", "system"],
            side_effect_level=3,
        )
    )
    TOOL_HANDLERS[name] = _noop_critical
    yield name
    tool_registry._capabilities.pop(name, None)
    TOOL_HANDLERS.pop(name, None)


@pytest.fixture
def failing_critical_tool(monkeypatch):
    name = "test_failing_critical_side_effect"
    tool_registry.register(
        ToolCapability(
            name=name,
            action_class="EXECUTE",
            allowed_agents=["ceo", "system"],
            side_effect_level=3,
        )
    )
    TOOL_HANDLERS[name] = _failing_critical
    yield name
    tool_registry._capabilities.pop(name, None)
    TOOL_HANDLERS.pop(name, None)


@pytest.mark.asyncio
async def test_system_execute_without_post_approval_flag_denied(critical_test_tool):
    result = await execute_tool(
        critical_test_tool,
        "system",
        "corr-system-denied",
        {"approval_id": "apr-1"},
    )
    assert result.success is False
    assert result.errors == ["SYSTEM_EXECUTE_NOT_AUTHORIZED"]


@pytest.mark.asyncio
async def test_system_agent_bypasses_policy_gate_with_post_approval(critical_test_tool):
    result = await execute_tool(
        critical_test_tool,
        "system",
        "corr-system-bypass",
        {"approval_id": "apr-1"},
        post_approval=True,
    )
    assert result.success is True
    assert "WAITING_APPROVAL" not in result.errors


@pytest.mark.asyncio
async def test_ceo_agent_escalates_critical_tool(critical_test_tool):
    result = await execute_tool(
        critical_test_tool,
        "ceo",
        "corr-ceo-escalate",
        {"approval_id": "apr-1"},
    )
    assert result.success is False
    assert result.errors == ["WAITING_APPROVAL"]


@pytest.mark.asyncio
async def test_execute_approved_action_uses_system_agent(critical_test_tool):
    reset_in_memory_store()
    proposal = create_immutable_proposal(
        correlation_id="corr-approved-exec",
        action=critical_test_tool,
        parameters={"payload": "demo"},
        agent="ceo",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary="Test critical execution",
        proposed_by="ceo",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    async def _work(conn):
        approval = await prepare_approval(conn, proposal, requester_agent="ceo")
        approval.status = ApprovalStatus.PENDING
        return await execute_approved_action(conn, approval, approved_by="reviewer")

    outcome = await run_mutative_session("corr-approved-exec", _work)
    assert outcome["execution"]["success"] is True
    assert outcome["execution"]["data"]["approval_id"]


@pytest.mark.asyncio
async def test_execute_approved_action_marks_execution_failed_on_tool_error(failing_critical_tool):
    reset_in_memory_store()
    proposal = create_immutable_proposal(
        correlation_id="corr-exec-failed",
        action=failing_critical_tool,
        parameters={"payload": "demo"},
        agent="ceo",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary="Test failing execution",
        proposed_by="ceo",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    async def _work(conn):
        from core.governance_store import load_approval

        approval = await prepare_approval(conn, proposal, requester_agent="ceo")
        outcome = await execute_approved_action(conn, approval, approved_by="reviewer")
        updated = await load_approval(conn, approval.id)
        return outcome, updated

    outcome, updated = await run_mutative_session("corr-exec-failed", _work)
    assert outcome["execution"]["success"] is False
    assert updated.status == ApprovalStatus.EXECUTION_FAILED
