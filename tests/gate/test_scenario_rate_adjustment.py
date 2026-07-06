"""Gate tests — FacilRentaCar rate adjustment scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.approval_service import execute_approved_action_in_session
from core.orchestrator import manual_orchestrator
from core.persistence import get_effects_by_correlation, reset_in_memory_store
from core.policy import policy_engine
from tests.fixtures.facilrentacar_mocks import patch_agent_runner_responses

DEMO = Path(__file__).resolve().parents[2] / "demo" / "fleet_occupancy_alert.json"


@pytest.fixture
def occupancy_event():
    return json.loads(DEMO.read_text())


@pytest.mark.asyncio
async def test_rate_never_exceeds_max_allowed(occupancy_event, fake_tool_router, mock_occupancy_agents):
    coo, cfo, ceo = mock_occupancy_agents
    with patch_agent_runner_responses(coo, cfo, ceo):
        await manual_orchestrator.run_domain_event(
            occupancy_event,
            session_id=occupancy_event["session_id"],
            correlation_id=occupancy_event["correlation_id"],
        )
    params = (await policy_engine.list_pending_approvals())[0].immutable_proposal.parameters
    max_rate = occupancy_event["current_base_rate_ars_per_day"] * (
        1 + occupancy_event["max_allowed_increase_pct"]
    )
    assert params["new_rate_ars_per_day"] <= max_rate


@pytest.mark.asyncio
async def test_multi_agent_chain_completes(occupancy_event, fake_tool_router, mock_occupancy_agents):
    coo, cfo, ceo = mock_occupancy_agents
    with patch_agent_runner_responses(coo, cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            occupancy_event,
            session_id=occupancy_event["session_id"],
            correlation_id=occupancy_event["correlation_id"],
        )
    assert result["runtime_state"] == "completed"
    assert result["approval"]["approval_id"]


@pytest.mark.asyncio
async def test_rollback_strategy_is_explicit(occupancy_event, fake_tool_router, mock_occupancy_agents):
    coo, cfo, ceo = mock_occupancy_agents
    with patch_agent_runner_responses(coo, cfo, ceo):
        await manual_orchestrator.run_domain_event(
            occupancy_event,
            session_id=occupancy_event["session_id"],
            correlation_id=occupancy_event["correlation_id"],
        )
    pending = await policy_engine.list_pending_approvals()
    assert pending[0].immutable_proposal.action == "publish_rate_adjustment"
    rollback = pending[0].immutable_proposal.rollback_strategy or ""
    assert "28,000" in rollback or "28000" in rollback


@pytest.mark.asyncio
async def test_rate_published_only_after_approval(
    occupancy_event, fake_tool_router, mock_occupancy_agents
):
    reset_in_memory_store()
    coo, cfo, ceo = mock_occupancy_agents
    with patch_agent_runner_responses(coo, cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            occupancy_event,
            session_id=occupancy_event["session_id"],
            correlation_id=occupancy_event["correlation_id"],
        )
    effects_before = await get_effects_by_correlation(occupancy_event["correlation_id"])
    assert not any(
        e.mutation_status == "complete" and "publish_rate_adjustment" in str(e.systems_affected)
        for e in effects_before
    )
    approval_id = result["approval"]["approval_id"]
    outcome = await execute_approved_action_in_session(
        approval_id,
        approved_by="reviewer",
        session_id=occupancy_event["session_id"],
    )
    assert outcome["execution"]["success"] is True
    effects_after = await get_effects_by_correlation(occupancy_event["correlation_id"])
    assert any(e.mutation_status == "complete" for e in effects_after)
