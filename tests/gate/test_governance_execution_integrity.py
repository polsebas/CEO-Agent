"""Gate: execution binding integrity — anti-tampering for execution_overrides."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.approval_service import (
    create_immutable_proposal,
    execute_approved_action,
    prepare_approval,
)
from core.persistence import get_effects_by_correlation, reset_in_memory_store
from core.runtime_session import run_mutative_session
from schemas.approvals import ApprovalStatus
from tools.registry import ToolCapability, tool_registry
from tools.router import TOOL_HANDLERS


async def _noop_discount(**kwargs):
    return {"ok": True, **kwargs}


@pytest.fixture
def discount_tool(monkeypatch):
    name = "apply_reservation_discount"
    if name not in tool_registry._capabilities:
        tool_registry.register(
            ToolCapability(
                name=name,
                action_class="EXECUTE",
                allowed_agents=["ceo", "system"],
                side_effect_level=3,
            )
        )
    TOOL_HANDLERS[name] = _noop_discount
    yield name


@pytest.fixture
def cancellation_tool(monkeypatch):
    name = "execute_cancellation_override"

    async def _noop_cancel(**kwargs):
        return {"ok": True, **kwargs}

    if name not in tool_registry._capabilities:
        tool_registry.register(
            ToolCapability(
                name=name,
                action_class="EXECUTE",
                allowed_agents=["ceo", "system"],
                side_effect_level=3,
            )
        )
    TOOL_HANDLERS[name] = _noop_cancel
    yield name


def _cancellation_proposal() -> object:
    return create_immutable_proposal(
        correlation_id="corr-cancel-bind",
        action="execute_cancellation_override",
        parameters={
            "client_id": "CORP-1",
            "reservation_ids": ["R-1"],
            "override_reason": "force majeure",
            "options": [
                {"option_id": "full_refund", "description": "Full refund"},
                {"option_id": "apply_penalty", "description": "Penalty"},
            ],
            "recommended_option": "full_refund",
        },
        agent="ceo",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary="Cancellation override",
        proposed_by="ceo",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_execution_overrides_cannot_change_discount_pct(discount_tool):
    reset_in_memory_store()
    proposal = create_immutable_proposal(
        correlation_id="corr-tamper-discount",
        action=discount_tool,
        parameters={"reservation_id": "R-1", "discount_pct": 0.10, "reason": "incident"},
        agent="ceo",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary="Discount 10%",
        proposed_by="ceo",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    async def _work(conn):
        approval = await prepare_approval(conn, proposal, requester_agent="ceo")
        with pytest.raises(ValueError, match="Execution overrides not allowed"):
            await execute_approved_action(
                conn,
                approval,
                approved_by="reviewer",
                execution_overrides={"discount_pct": 0.99},
            )

    await run_mutative_session("corr-tamper-discount", _work)


@pytest.mark.asyncio
async def test_cancellation_requires_override_type(cancellation_tool):
    reset_in_memory_store()
    proposal = _cancellation_proposal()

    async def _work(conn):
        approval = await prepare_approval(conn, proposal, requester_agent="ceo")
        with pytest.raises(ValueError, match="override_type required"):
            await execute_approved_action(conn, approval, approved_by="reviewer")

    await run_mutative_session("corr-cancel-bind", _work)
    effects = await get_effects_by_correlation("corr-cancel-bind")
    assert not any(e.mutation_status == "complete" for e in effects)


@pytest.mark.asyncio
async def test_cancellation_invalid_override_type_rejected(cancellation_tool):
    reset_in_memory_store()
    proposal = _cancellation_proposal()

    async def _work(conn):
        approval = await prepare_approval(conn, proposal, requester_agent="ceo")
        with pytest.raises(ValueError, match="Invalid override_type"):
            await execute_approved_action(
                conn,
                approval,
                approved_by="reviewer",
                execution_overrides={"override_type": "free_car_for_life"},
            )

    await run_mutative_session("corr-cancel-bind", _work)
