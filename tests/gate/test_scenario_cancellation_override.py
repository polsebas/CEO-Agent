"""Gate tests — FacilRentaCar cancellation override scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.approval_service import execute_approved_action_in_session
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.policy import policy_engine
from tests.fixtures.facilrentacar_mocks import patch_agent_runner_responses

DEMO = Path(__file__).resolve().parents[2] / "demo" / "cancellation_override.json"


@pytest.fixture
def cancellation_event():
    return json.loads(DEMO.read_text())


@pytest.mark.asyncio
async def test_override_requires_founder_approval(cancellation_event, fake_tool_router, mock_cancellation_agents):
    cfo, ceo = mock_cancellation_agents
    with patch_agent_runner_responses(cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            cancellation_event,
            session_id=cancellation_event["session_id"],
            correlation_id=cancellation_event["correlation_id"],
        )
    assert result["approval"]["approval_id"]
    pending = await policy_engine.list_pending_approvals()
    assert pending[0].immutable_proposal.side_effect_level == "EXECUTE_CRITICAL"


@pytest.mark.asyncio
async def test_both_options_present_in_proposal(
    cancellation_event, fake_tool_router, mock_cancellation_agents
):
    cfo, ceo = mock_cancellation_agents
    with patch_agent_runner_responses(cfo, ceo):
        await manual_orchestrator.run_domain_event(
            cancellation_event,
            session_id=cancellation_event["session_id"],
            correlation_id=cancellation_event["correlation_id"],
        )
    options = (await policy_engine.list_pending_approvals())[0].immutable_proposal.parameters["options"]
    option_ids = {o["option_id"] for o in options}
    assert option_ids == {"full_refund", "apply_penalty"}


@pytest.mark.asyncio
async def test_approved_option_matches_outbox_payload(
    cancellation_event, fake_tool_router, mock_cancellation_agents
):
    reset_in_memory_store()
    cfo, ceo = mock_cancellation_agents
    with patch_agent_runner_responses(cfo, ceo):
        result = await manual_orchestrator.run_domain_event(
            cancellation_event,
            session_id=cancellation_event["session_id"],
            correlation_id=cancellation_event["correlation_id"],
        )
    approval_id = result["approval"]["approval_id"]
    outcome = await execute_approved_action_in_session(
        approval_id,
        approved_by="reviewer",
        session_id=cancellation_event["session_id"],
        execution_overrides={"override_type": "full_refund"},
    )
    assert outcome["execution"]["success"] is True
    assert outcome["execution"]["data"]["override_type"] == "full_refund"
