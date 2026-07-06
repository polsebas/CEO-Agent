"""Gate tests — FacilRentaCar compensation scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.approval_service import execute_approved_action_in_session, reject_approval_in_session
from core.orchestrator import manual_orchestrator
from core.persistence import get_effects_by_correlation, reset_in_memory_store
from core.policy import policy_engine
from schemas.approvals import ApprovalStatus
from tests.fixtures.facilrentacar_mocks import patch_agent_runner_responses

DEMO = Path(__file__).resolve().parents[2] / "demo" / "compensation_request.json"


@pytest.fixture
def compensation_event():
    return json.loads(DEMO.read_text())


@pytest.mark.asyncio
async def test_compensation_requires_approval_before_effect(
    compensation_event, fake_tool_router, mock_compensation_agents
):
    cfo, ceo = mock_compensation_agents
    with patch_agent_runner_responses(cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            compensation_event,
            session_id=compensation_event["session_id"],
            correlation_id=compensation_event["correlation_id"],
        )
    assert result.get("approval", {}).get("approval_id")
    effects = await get_effects_by_correlation(compensation_event["correlation_id"])
    completed = [e for e in effects if e.mutation_status == "complete" and "discount" in str(e.systems_affected)]
    assert completed == []


@pytest.mark.asyncio
async def test_compensation_approval_creates_binding(
    compensation_event, fake_tool_router, mock_compensation_agents
):
    cfo, ceo = mock_compensation_agents
    with patch_agent_runner_responses(cfo, ceo):
        await manual_orchestrator.run_domain_event(
            compensation_event,
            session_id=compensation_event["session_id"],
            correlation_id=compensation_event["correlation_id"],
        )
    pending = await policy_engine.list_pending_approvals()
    assert len(pending) == 1
    approval = pending[0]
    assert approval.binding is not None
    assert approval.immutable_proposal.checksum
    assert approval.immutable_proposal.side_effect_level == "EXECUTE_CRITICAL"


@pytest.mark.asyncio
async def test_compensation_rejection_leaves_no_effect(
    compensation_event, fake_tool_router, mock_compensation_agents
):
    cfo, ceo = mock_compensation_agents
    with patch_agent_runner_responses(cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            compensation_event,
            session_id=compensation_event["session_id"],
            correlation_id=compensation_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    rejected = await reject_approval_in_session(
        approval_id,
        rejected_by="reviewer",
        session_id=compensation_event["session_id"],
        reason="Descuento no justificado",
    )
    assert rejected.status == ApprovalStatus.REJECTED
    effects = await get_effects_by_correlation(compensation_event["correlation_id"])
    assert not any(e.mutation_status == "complete" for e in effects)


@pytest.mark.asyncio
async def test_compensation_approved_executes_with_approval_id(
    compensation_event, fake_tool_router, mock_compensation_agents
):
    reset_in_memory_store()
    cfo, ceo = mock_compensation_agents
    with patch_agent_runner_responses(cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            compensation_event,
            session_id=compensation_event["session_id"],
            correlation_id=compensation_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    outcome = await execute_approved_action_in_session(
        approval_id,
        approved_by="reviewer",
        session_id=compensation_event["session_id"],
    )
    assert outcome["execution"]["success"] is True
    assert outcome["execution"]["data"]["approval_id"] == approval_id
