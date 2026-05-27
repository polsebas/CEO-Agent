"""Experimental specialist agents — NOT part of production runtime (RRM-1)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.agent_registry import AgentDisabledError, assert_agent_active
from core.confidence import calibrate_confidence
from core.orchestrator import manual_orchestrator
from core.runtime_session import run_mutative_session
from core.transaction import PersistRuntimePayload, persist_runtime_tx
from schemas.decisions import DecisionRecord
from schemas.messages import AgentMessage, AgentRole
from schemas.responses import CFOResponse, CMOResponse, COOResponse
from schemas.runtime import RuntimeState
from tools.router import execute_tool


async def delegate_to_cfo(message: AgentMessage, session_id: str) -> dict:
    assert_agent_active("cfo")
    sm = manual_orchestrator._make_state_machine(message.correlation_id, session_id)
    cashflow = await execute_tool("get_cashflow_summary", "cfo", message.correlation_id)
    runway = await execute_tool("calculate_runway", "cfo", message.correlation_id)
    response = CFOResponse(
        summary=f"Financial analysis: {message.payload.get('objective', '')}",
        cashflow_status="negative" if (cashflow.data or {}).get("net_cashflow", 0) < 0 else "positive",
        runway_months=(runway.data or {}).get("runway_months", 0),
        recommendations=["Reduce burn rate", "Review subscription pricing"],
    )
    return await _save_specialist_result(message, session_id, sm, "cfo", response.summary, response.model_dump())


async def delegate_to_coo(message: AgentMessage, session_id: str) -> dict:
    assert_agent_active("coo")
    sm = manual_orchestrator._make_state_machine(message.correlation_id, session_id)
    blockers = await execute_tool("detect_blockers", "coo", message.correlation_id)
    tasks = await execute_tool("list_active_tasks", "coo", message.correlation_id)
    response = COOResponse(
        summary=f"Operations review: {message.payload.get('objective', '')}",
        blockers=(blockers.data or {}).get("blockers", []),
        task_status=f"{len((tasks.data or {}).get('tasks', []))} active tasks",
        bottlenecks=(blockers.data or {}).get("blockers", []),
    )
    return await _save_specialist_result(message, session_id, sm, "coo", response.summary, response.model_dump())


async def delegate_to_cmo(message: AgentMessage, session_id: str) -> dict:
    assert_agent_active("cmo")
    sm = manual_orchestrator._make_state_machine(message.correlation_id, session_id)
    analytics = await execute_tool("get_analytics_summary", "cmo", message.correlation_id)
    response = CMOResponse(
        summary=f"Growth analysis: {message.payload.get('objective', '')}",
        campaign_status="2 active campaigns",
        cac_analysis={"cac_usd": (analytics.data or {}).get("cac_usd", 0)},
        conversion_funnel={"rate": (analytics.data or {}).get("conversion_rate", 0)},
        recommendations=["Optimize landing page conversion"],
    )
    return await _save_specialist_result(message, session_id, sm, "cmo", response.summary, response.model_dump())


async def _save_specialist_result(
    message: AgentMessage,
    session_id: str,
    sm,
    agent_id: str,
    summary: str,
    structured: dict,
) -> dict:
    decision = DecisionRecord(
        id=str(uuid4()),
        correlation_id=message.correlation_id,
        causation_id=message.id,
        objective=message.payload.get("objective", ""),
        reasoning_summary=summary,
        confidence=calibrate_confidence(),
        final_action=f"delegate:{agent_id}",
        outcome="success",
        agent=agent_id,
        runtime_state=sm.state,
        created_at=datetime.now(timezone.utc),
    )
    async def _persist(conn):
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=message.correlation_id,
                session_id=session_id,
                event_type="decision.recorded",
                event_payload=decision.model_dump(mode="json"),
                causation_id=message.id,
                decision=decision,
                business_key=f"decision:{decision.id}",
            ),
        )

    await run_mutative_session(session_id, _persist)
    sm.transition(RuntimeState.COMPLETED)
    return {"decision_id": decision.id, "summary": summary, "structured_response": structured}


DELEGATE_MAP = {
    AgentRole.CFO: delegate_to_cfo,
    AgentRole.COO: delegate_to_coo,
    AgentRole.CMO: delegate_to_cmo,
    AgentRole.CTO: manual_orchestrator.delegate_to_specialist,
}
