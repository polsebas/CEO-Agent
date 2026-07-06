"""FacilRentaCar domain event handlers — governance-first multi-agent flows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agents.factory import create_ceo_agent, create_cfo_agent, create_coo_agent
from core.agent_runner import structured_agent_runner
from core.approval_service import create_immutable_proposal, prepare_approval
from core.confidence import calibrate_confidence
from core.persistence import get_world_state
from core.transaction import PersistRuntimePayload, persist_runtime_tx
from schemas.decisions import DecisionRecord
from schemas.responses import CEOResponse, CFOResponse, COOResponse, CancellationOption
from schemas.runtime import RuntimeState
from schemas.tools import ToolResult
from tools.router import execute_tool

if TYPE_CHECKING:
    from core.orchestrator import ManualOrchestrator
    from core.runtime import RuntimeStateMachine

APPROVAL_TTL_STANDARD = timedelta(hours=24)
APPROVAL_TTL_CRITICAL = timedelta(hours=2)

EVENT_HANDLERS = {}


def register_handler(event_type: str):
    def decorator(fn):
        EVENT_HANDLERS[event_type] = fn
        return fn

    return decorator


@dataclass
class ToolCall:
    name: str
    params: dict
    label: str


class RuntimeHandlerError(RuntimeError):
    """Raised when a FacilRentaCar handler cannot proceed (e.g. READ tool failure)."""


async def run_agent_with_tools(
    orchestrator: ManualOrchestrator,
    conn: Any,
    *,
    agent_id: str,
    response_model: type,
    base_prompt: str,
    tool_calls: list[ToolCall],
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
    step_id: int = 0,
) -> tuple[Any, list[ToolResult], dict[str, list[str]]]:
    tool_results: list[ToolResult] = []
    tools_used_by: dict[str, list[str]] = {agent_id: []}
    enriched_sections: list[str] = []

    for call in tool_calls:
        if sm.state == RuntimeState.OBSERVING:
            await orchestrator._record_transition(conn, sm, RuntimeState.REASONING, session_id)
        await orchestrator._record_transition(conn, sm, RuntimeState.WAITING_TOOL, session_id)
        result = await execute_tool(
            call.name,
            agent_id,
            correlation_id,
            call.params,
            session_id=session_id,
        )
        tool_results.append(result)
        tools_used_by[agent_id].append(call.name)
        sm._session_tool_names.append(call.name)
        if not result.success:
            raise RuntimeHandlerError(f"Tool {call.name} failed: {result.errors}")
        enriched_sections.append(f"## {call.label}\n{json.dumps(result.data or {}, ensure_ascii=False)}")
        await orchestrator._record_transition(conn, sm, RuntimeState.OBSERVING, session_id)

    prompt = f"{base_prompt}\n\n" + "\n\n".join(enriched_sections)
    policy = await orchestrator._resolve_adaptive_policy(conn, session_id, correlation_id, sm)
    budget = orchestrator._cognitive_budget(policy=policy)

    agent_factory = {"cfo": create_cfo_agent, "coo": create_coo_agent, "ceo": create_ceo_agent}
    agent = agent_factory[agent_id]()
    response, _trace, _tel = await structured_agent_runner.run(
        agent,
        prompt,
        response_model,
        correlation_id,
        session_id=session_id,
        agent_id=agent_id,
        step_id=step_id,
        budget=budget,
    )
    return response, tool_results, tools_used_by


async def _persist_decision(
    conn: Any,
    *,
    session_id: str,
    correlation_id: str,
    objective: str,
    agent: str,
    summary: str,
    tools_used: list[str],
    tools_used_by: dict[str, list[str]],
    sm: RuntimeStateMachine,
    final_action: str,
) -> DecisionRecord:
    decision = DecisionRecord(
        id=str(uuid4()),
        correlation_id=correlation_id,
        objective=objective,
        tools_used=tools_used,
        tools_used_by=tools_used_by,
        reasoning_summary=summary,
        confidence=calibrate_confidence(deterministic_checks=0.85),
        final_action=final_action,
        outcome="pending",
        agent=agent,
        runtime_state=sm.state,
        created_at=datetime.now(timezone.utc),
    )
    await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=correlation_id,
            session_id=session_id,
            event_type="decision.recorded",
            event_payload=decision.model_dump(mode="json"),
            decision=decision,
            business_key=f"decision:{decision.id}",
        ),
    )
    return decision


async def _prepare_critical_proposal(
    conn: Any,
    *,
    correlation_id: str,
    session_id: str,
    action: str,
    parameters: dict,
    impact_summary: str,
    rollback_strategy: str,
    ttl: timedelta,
) -> dict:
    proposal = create_immutable_proposal(
        correlation_id=correlation_id,
        action=action,
        parameters=parameters,
        agent="ceo",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary=impact_summary,
        proposed_by="ceo",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + ttl,
        task_id=session_id,
        rollback_strategy=rollback_strategy,
    )
    approval = await prepare_approval(
        conn,
        proposal,
        requester_agent="ceo",
        session_id=session_id,
    )
    return {"approval_id": approval.id, "proposal": proposal}


@register_handler("vehicle_incident_reported")
async def handle_vehicle_incident(
    orchestrator: ManualOrchestrator,
    conn: Any,
    event: dict,
    *,
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
) -> dict:
    reservation_id = event["reservation_id"]
    cfo_response, cfo_tools, tools_map = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="cfo",
        response_model=CFOResponse,
        base_prompt=f"Incidencia vehículo en reserva {reservation_id}. Evento: {json.dumps(event)}",
        tool_calls=[
            ToolCall("get_reservation_detail", {"reservation_id": reservation_id}, "Detalle reserva"),
            ToolCall("get_compensation_policy", {}, "Política compensación"),
        ],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
    )
    discount_pct = cfo_response.discount_pct
    if discount_pct is None:
        max_pct = event.get("policy_max_compensation_pct", 0.20)
        discount_pct = min(max_pct, 0.12)
    discount_amount = cfo_response.discount_amount_ars or event["reservation_amount_ars"] * discount_pct

    ceo_response, _, ceo_tools = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="ceo",
        response_model=CEOResponse,
        base_prompt=(
            f"Decisión compensación reserva {reservation_id}. "
            f"CFO: {cfo_response.model_dump()}"
        ),
        tool_calls=[],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
        step_id=1,
    )
    tools_map.update(ceo_tools)
    all_tools = [t for names in tools_map.values() for t in names]

    await _persist_decision(
        conn,
        session_id=session_id,
        correlation_id=correlation_id,
        objective=f"Compensación incidencia {reservation_id}",
        agent="ceo",
        summary=ceo_response.summary or cfo_response.summary,
        tools_used=all_tools,
        tools_used_by=tools_map,
        sm=sm,
        final_action="apply_reservation_discount",
    )

    approval = await _prepare_critical_proposal(
        conn,
        correlation_id=correlation_id,
        session_id=session_id,
        action="apply_reservation_discount",
        parameters={
            "reservation_id": reservation_id,
            "discount_pct": discount_pct,
            "reason": cfo_response.justification or event.get("incident_description", "compensation"),
        },
        impact_summary=(
            f"Descuento {discount_pct * 100:.0f}% sobre reserva {reservation_id} — "
            f"ARS {discount_amount:,.0f}"
        ),
        rollback_strategy="No se aplica descuento. La reserva continúa con el monto original.",
        ttl=APPROVAL_TTL_STANDARD,
    )
    return {"event_type": event["event_type"], "approval": approval, "session_id": session_id}


@register_handler("fleet_maintenance_completed")
async def handle_fleet_reactivation(
    orchestrator: ManualOrchestrator,
    conn: Any,
    event: dict,
    *,
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
) -> dict:
    branches = event.get("branches_affected", [])
    tool_calls: list[ToolCall] = []
    for branch in branches:
        tool_calls.append(ToolCall("get_branch_status", {"branch_name": branch}, f"Estado {branch}"))
        tool_calls.append(
            ToolCall(
                "get_pending_reservations_by_branch",
                {"branch_name": branch},
                f"Pendientes {branch}",
            )
        )

    coo_response, _, tools_map = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="coo",
        response_model=COOResponse,
        base_prompt=f"Reactivación flota post-mantenimiento: {json.dumps(event)}",
        tool_calls=tool_calls,
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
    )

    vehicles_to_activate = coo_response.vehicles_to_activate_now
    if not vehicles_to_activate:
        returned = [v["id"] for v in event.get("vehicles_returned", [])]
        hold = set(coo_response.vehicles_to_hold or [])
        vehicles_to_activate = [v for v in returned if v not in hold][:3]

    ceo_response, _, ceo_tools = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="ceo",
        response_model=CEOResponse,
        base_prompt=f"Aprueba reactivación. COO: {coo_response.model_dump()}",
        tool_calls=[],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
        step_id=1,
    )
    tools_map.update(ceo_tools)
    branches_str = ", ".join(branches)
    hold_count = len(coo_response.vehicles_to_hold or [])

    await _persist_decision(
        conn,
        session_id=session_id,
        correlation_id=correlation_id,
        objective="Reactivación flota post-mantenimiento",
        agent="ceo",
        summary=ceo_response.summary or coo_response.summary,
        tools_used=[t for names in tools_map.values() for t in names],
        tools_used_by=tools_map,
        sm=sm,
        final_action="activate_vehicles",
    )

    approval = await _prepare_critical_proposal(
        conn,
        correlation_id=correlation_id,
        session_id=session_id,
        action="activate_vehicles",
        parameters={
            "vehicle_ids": vehicles_to_activate,
            "activation_notes": coo_response.operational_notes or "Reactivación aprobada por CEO",
        },
        impact_summary=(
            f"REACTIVACIÓN FLOTA — {len(vehicles_to_activate)} vehículos\n"
            f"Sucursales: {branches_str}\n"
            f"Vehículos en hold: {hold_count}"
        ),
        rollback_strategy="Mantener vehículos en estado en_revision. No publicar disponibilidad.",
        ttl=APPROVAL_TTL_STANDARD,
    )
    return {"event_type": event["event_type"], "approval": approval, "session_id": session_id}


@register_handler("fleet_occupancy_critical")
async def handle_fleet_occupancy(
    orchestrator: ManualOrchestrator,
    conn: Any,
    event: dict,
    *,
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
) -> dict:
    categories = event.get("categories_affected", ["SUV"])
    coo_response, _, tools_map = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="coo",
        response_model=COOResponse,
        base_prompt=f"Alerta ocupación crítica: {json.dumps(event)}",
        tool_calls=[
            ToolCall(
                "get_fleet_occupancy",
                {"period_start": event["period_start"], "period_end": event["period_end"]},
                "Ocupación flota",
            ),
        ],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
    )

    cfo_response, _, cfo_tools = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="cfo",
        response_model=CFOResponse,
        base_prompt=f"Pricing dinámico. COO: {coo_response.model_dump()} Evento: {json.dumps(event)}",
        tool_calls=[
            ToolCall("get_current_rates", {"categories": categories}, "Tarifas actuales"),
            ToolCall("get_market_rates", {"categories": categories}, "Tarifas mercado"),
        ],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
        step_id=1,
    )
    tools_map.update(cfo_tools)

    base_rate = event["current_base_rate_ars_per_day"]
    max_pct = event.get("max_allowed_increase_pct", 0.35)
    approved_rate = cfo_response.recommended_rate or ceo_fallback_rate(base_rate, max_pct)
    approved_rate = min(approved_rate, base_rate * (1 + max_pct))

    ceo_response, _, ceo_tools = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="ceo",
        response_model=CEOResponse,
        base_prompt=f"Decisión tarifas. CFO: {cfo_response.model_dump()}",
        tool_calls=[],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
        step_id=2,
    )
    tools_map.update(ceo_tools)
    if ceo_response.approved_rate:
        approved_rate = min(ceo_response.approved_rate, base_rate * (1 + max_pct))

    await _persist_decision(
        conn,
        session_id=session_id,
        correlation_id=correlation_id,
        objective="Ajuste tarifas por ocupación crítica",
        agent="ceo",
        summary=ceo_response.summary or cfo_response.summary,
        tools_used=[t for names in tools_map.values() for t in names],
        tools_used_by=tools_map,
        sm=sm,
        final_action="publish_rate_adjustment",
    )

    approval = await _prepare_critical_proposal(
        conn,
        correlation_id=correlation_id,
        session_id=session_id,
        action="publish_rate_adjustment",
        parameters={
            "categories": categories,
            "new_rate_ars_per_day": approved_rate,
            "valid_from": event["period_start"],
            "valid_to": event["period_end"],
            "adjustment_reason": f"Ocupación crítica {event['current_occupancy_pct'] * 100:.0f}%",
            "previous_rate_ars_per_day": base_rate,
        },
        impact_summary=(
            f"Ajuste tarifas {categories} — ARS {approved_rate:,.0f}/día "
            f"(base ARS {base_rate:,.0f})"
        ),
        rollback_strategy=f"Revertir a tarifas anteriores: ARS {base_rate:,.0f}/día",
        ttl=APPROVAL_TTL_CRITICAL,
    )
    return {"event_type": event["event_type"], "approval": approval, "session_id": session_id}


def ceo_fallback_rate(base_rate: float, max_pct: float) -> float:
    return round(base_rate * (1 + min(max_pct, 0.15)), 2)


@register_handler("corporate_cancellation_override_request")
async def handle_cancellation_override(
    orchestrator: ManualOrchestrator,
    conn: Any,
    event: dict,
    *,
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
) -> dict:
    client_id = event["client_id"]
    cfo_response, _, tools_map = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="cfo",
        response_model=CFOResponse,
        base_prompt=f"Override cancelación corporativa: {json.dumps(event)}",
        tool_calls=[
            ToolCall("get_client_history", {"client_id": client_id}, "Historial cliente"),
            ToolCall("get_cancellation_policy", {}, "Política cancelación"),
        ],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
    )

    total = event["total_cancellation_amount_ars"]
    penalty_pct = event.get("cancellation_policy_penalty_pct", 0.30)
    penalty_amount = total * penalty_pct
    ltv = event.get("client_revenue_ytd_ars", 0) / max(event.get("client_history_months", 1), 1) * 24

    options = [
        CancellationOption(
            option_id="full_refund",
            description="Reembolso completo (excepción fuerza mayor)",
            financial_impact_ars=total,
            client_relationship_impact="positive",
            recommendation_score=0.8 if ltv > penalty_amount * 10 else 0.5,
        ),
        CancellationOption(
            option_id="apply_penalty",
            description="Aplicar penalidad contractual",
            financial_impact_ars=penalty_amount,
            client_relationship_impact="negative",
            recommendation_score=0.4,
        ),
    ]

    ceo_response, _, ceo_tools = await run_agent_with_tools(
        orchestrator,
        conn,
        agent_id="ceo",
        response_model=CEOResponse,
        base_prompt=(
            f"Decisión override cancelación. CFO: {cfo_response.model_dump()} "
            f"Opciones: {[o.model_dump() for o in options]}"
        ),
        tool_calls=[],
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
        step_id=1,
    )
    tools_map.update(ceo_tools)
    recommended = ceo_response.recommended_option or (
        "full_refund" if ltv > penalty_amount * 10 else "apply_penalty"
    )
    if ceo_response.cancellation_options:
        options = ceo_response.cancellation_options

    reservation_ids = [r["id"] for r in event.get("reservations_to_cancel", [])]
    impact_summary = (
        f"OVERRIDE CANCELACIÓN — {event['client_name']}\n"
        f"Opción recomendada: {recommended}\n"
        f"Monto en juego: ARS {total:,.0f}\n"
        f"Penalidad contractual: ARS {penalty_amount:,.0f}\n"
        f"LTV estimado cliente: ARS {ltv:,.0f}\n"
        f"Razón: {ceo_response.reasoning or ceo_response.summary}"
    )

    await _persist_decision(
        conn,
        session_id=session_id,
        correlation_id=correlation_id,
        objective=f"Override cancelación {client_id}",
        agent="ceo",
        summary=ceo_response.summary,
        tools_used=[t for names in tools_map.values() for t in names],
        tools_used_by=tools_map,
        sm=sm,
        final_action="execute_cancellation_override",
    )

    approval = await _prepare_critical_proposal(
        conn,
        correlation_id=correlation_id,
        session_id=session_id,
        action="execute_cancellation_override",
        parameters={
            "client_id": client_id,
            "reservation_ids": reservation_ids,
            "override_reason": event.get("force_majeure_document", "corporate override"),
            "options": [o.model_dump() for o in options],
            "recommended_option": recommended,
        },
        impact_summary=impact_summary,
        rollback_strategy="Aplicar penalidad contractual estándar sin override.",
        ttl=APPROVAL_TTL_CRITICAL,
    )
    return {"event_type": event["event_type"], "approval": approval, "session_id": session_id}


async def dispatch_facilrentacar_event(
    orchestrator: ManualOrchestrator,
    conn: Any,
    event: dict,
    *,
    session_id: str,
    correlation_id: str,
    sm: RuntimeStateMachine,
) -> dict:
    handler = EVENT_HANDLERS.get(event.get("event_type", ""))
    if not handler:
        raise ValueError(f"Unknown event_type: {event.get('event_type')}")
    return await handler(
        orchestrator,
        conn,
        event,
        session_id=session_id,
        correlation_id=correlation_id,
        sm=sm,
    )
