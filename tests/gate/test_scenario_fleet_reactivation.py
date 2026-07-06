"""Gate tests — FacilRentaCar fleet reactivation scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.approval_service import execute_approved_action_in_session
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.policy import policy_engine
from tests.fixtures.facilrentacar_mocks import patch_agent_runner_responses

DEMO = Path(__file__).resolve().parents[2] / "demo" / "fleet_reactivation.json"


@pytest.fixture
def reactivation_event():
    return json.loads(DEMO.read_text())


@pytest.mark.asyncio
async def test_activation_requires_approval(reactivation_event, fake_tool_router, mock_reactivation_agents):
    coo, ceo = mock_reactivation_agents
    with patch_agent_runner_responses(coo, ceo):
        result = await manual_orchestrator.run_domain_event(
            reactivation_event,
            session_id=reactivation_event["session_id"],
            correlation_id=reactivation_event["correlation_id"],
        )
    assert result["approval"]["approval_id"]
    pending = await policy_engine.list_pending_approvals()
    assert len(pending) == 1


@pytest.mark.asyncio
async def test_hold_vehicles_not_in_outbox(reactivation_event, fake_tool_router, mock_reactivation_agents):
    coo, ceo = mock_reactivation_agents
    with patch_agent_runner_responses(coo, ceo):
        result = await manual_orchestrator.run_domain_event(
            reactivation_event,
            session_id=reactivation_event["session_id"],
            correlation_id=reactivation_event["correlation_id"],
        )
    params = (await policy_engine.list_pending_approvals())[0].immutable_proposal.parameters
    assert "VEH-401" not in params.get("vehicle_ids", [])


@pytest.mark.asyncio
async def test_activation_payload_matches_approved_list(
    reactivation_event, fake_tool_router, mock_reactivation_agents
):
    reset_in_memory_store()
    coo, ceo = mock_reactivation_agents
    with patch_agent_runner_responses(coo, ceo):
        result = await manual_orchestrator.run_domain_event(
            reactivation_event,
            session_id=reactivation_event["session_id"],
            correlation_id=reactivation_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    outcome = await execute_approved_action_in_session(
        approval_id,
        approved_by="reviewer",
        session_id=reactivation_event["session_id"],
    )
    assert outcome["execution"]["success"] is True
    assert set(outcome["execution"]["data"]["vehicle_ids"]) == {"VEH-205", "VEH-206"}
