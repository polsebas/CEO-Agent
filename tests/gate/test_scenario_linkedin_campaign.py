"""Gate tests — FacilRentaCar LinkedIn B2B campaign scenario."""

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

DEMO = Path(__file__).resolve().parents[2] / "demo" / "linkedin_campaign_request.json"


@pytest.fixture
def linkedin_event():
    return json.loads(DEMO.read_text())


@pytest.mark.asyncio
async def test_linkedin_requires_approval_before_effect(
    linkedin_event, fake_tool_router, mock_linkedin_agents
):
    cmo, ceo = mock_linkedin_agents
    with patch_agent_runner_responses(cmo, ceo):
        result = await manual_orchestrator.run_domain_event(
            linkedin_event,
            session_id=linkedin_event["session_id"],
            correlation_id=linkedin_event["correlation_id"],
        )
    assert result.get("approval", {}).get("approval_id")
    effects = await get_effects_by_correlation(linkedin_event["correlation_id"])
    completed = [
        e for e in effects if e.mutation_status == "complete" and "linkedin" in str(e.systems_affected)
    ]
    assert completed == []


@pytest.mark.asyncio
async def test_linkedin_approval_creates_binding(
    linkedin_event, fake_tool_router, mock_linkedin_agents
):
    cmo, ceo = mock_linkedin_agents
    with patch_agent_runner_responses(cmo, ceo):
        await manual_orchestrator.run_domain_event(
            linkedin_event,
            session_id=linkedin_event["session_id"],
            correlation_id=linkedin_event["correlation_id"],
        )
    pending = await policy_engine.list_pending_approvals()
    assert len(pending) == 1
    approval = pending[0]
    assert approval.binding is not None
    assert approval.immutable_proposal.checksum
    assert approval.immutable_proposal.side_effect_level == "EXECUTE_CRITICAL"


@pytest.mark.asyncio
async def test_linkedin_rejection_leaves_no_effect(
    linkedin_event, fake_tool_router, mock_linkedin_agents
):
    cmo, ceo = mock_linkedin_agents
    with patch_agent_runner_responses(cmo, ceo):
        result = await manual_orchestrator.run_domain_event(
            linkedin_event,
            session_id=linkedin_event["session_id"],
            correlation_id=linkedin_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    rejected = await reject_approval_in_session(
        approval_id,
        rejected_by="reviewer",
        session_id=linkedin_event["session_id"],
        reason="Budget not justified this quarter",
    )
    assert rejected.status == ApprovalStatus.REJECTED
    effects = await get_effects_by_correlation(linkedin_event["correlation_id"])
    assert not any(e.mutation_status == "complete" for e in effects)


@pytest.mark.asyncio
async def test_linkedin_approved_executes_with_approval_id(
    linkedin_event, fake_tool_router, mock_linkedin_agents
):
    reset_in_memory_store()
    cmo, ceo = mock_linkedin_agents
    with patch_agent_runner_responses(cmo, ceo):
        result = await manual_orchestrator.run_domain_event(
            linkedin_event,
            session_id=linkedin_event["session_id"],
            correlation_id=linkedin_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    outcome = await execute_approved_action_in_session(
        approval_id,
        approved_by="reviewer",
        session_id=linkedin_event["session_id"],
    )
    assert outcome["execution"]["success"] is True
    assert outcome["execution"]["data"]["approval_id"] == approval_id
