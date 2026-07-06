"""Smoke tests — seed_demo wiring for MVP and FacilRentaCar scenarios."""

from __future__ import annotations

import pytest

from core.policy import policy_engine
from scripts.seed_demo import MVP_FIXTURES, SCENARIO_FILES, seed_demo
from tests.fixtures.facilrentacar_mocks import patch_agent_runner_responses


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_seed_default_mvp_only_no_facilrentacar_approvals(
    fake_tool_router,
    mock_compensation_agents,
):
    with patch_agent_runner_responses(*mock_compensation_agents):
        results = await seed_demo()
    assert len(results) == len(MVP_FIXTURES)
    pending = await policy_engine.list_pending_approvals()
    assert pending == []


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", list(SCENARIO_FILES.keys()))
@pytest.mark.asyncio
async def test_seed_scenario_produces_pending_approval(
    scenario,
    fake_tool_router,
    mock_compensation_agents,
    mock_reactivation_agents,
    mock_occupancy_agents,
    mock_cancellation_agents,
):
    mocks = {
        "compensation": mock_compensation_agents,
        "reactivation": mock_reactivation_agents,
        "occupancy": mock_occupancy_agents,
        "cancellation": mock_cancellation_agents,
    }
    agents = mocks[scenario]
    with patch_agent_runner_responses(*agents):
        await seed_demo(scenario=scenario)
    pending = await policy_engine.list_pending_approvals()
    assert len(pending) == 1
    assert pending[0].immutable_proposal.side_effect_level == "EXECUTE_CRITICAL"
