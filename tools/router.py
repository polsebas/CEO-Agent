"""Tool router with permission validation and cache."""

from __future__ import annotations

from core.cache import cache_get, cache_set
from core.canonical import canonical_json
from core.policy import PolicyDecision, policy_engine
from schemas.approvals import ActionProposal
from schemas.tools import ToolResult
from tools.github.client import analyze_incidents, get_repo_health, list_github_prs, prioritize_bugs
from tools.normalizer import normalize_tool_call
from tools.registry import tool_registry
from tools.stubs.business import (
    calculate_runway,
    create_initiative,
    detect_blockers,
    escalate_to_human,
    get_analytics_summary,
    get_cashflow_summary,
    list_active_tasks,
    propose_campaign,
    read_kpi_dashboard,
)

TOOL_HANDLERS = {
    "list_github_prs": list_github_prs,
    "get_repo_health": get_repo_health,
    "analyze_incidents": analyze_incidents,
    "prioritize_bugs": prioritize_bugs,
    "read_kpi_dashboard": read_kpi_dashboard,
    "get_cashflow_summary": get_cashflow_summary,
    "calculate_runway": calculate_runway,
    "detect_blockers": detect_blockers,
    "list_active_tasks": list_active_tasks,
    "get_analytics_summary": get_analytics_summary,
    "propose_campaign": propose_campaign,
    "create_initiative": create_initiative,
    "escalate_to_human": escalate_to_human,
}

CACHEABLE = {"list_github_prs", "get_repo_health", "read_kpi_dashboard", "calculate_runway", "get_cashflow_summary"}


def _canonical_params(params: dict | None) -> dict:
    if not params:
        return {}
    import json

    return json.loads(canonical_json(params, strip_volatile=False))


async def execute_tool(
    tool_name: str,
    agent_id: str,
    correlation_id: str,
    params: dict | None = None,
    *,
    session_id: str | None = None,
) -> ToolResult:
    from core.spans import span_manager
    from schemas.spans import SpanStatus, SpanType

    tspan = span_manager.start(
        SpanType.TOOL_EXECUTION,
        metadata={"tool_name": tool_name, "agent_id": agent_id},
    )
    params = _canonical_params(params)
    cap = tool_registry.get(tool_name)
    if not cap:
        span_manager.end(tspan, status=SpanStatus.ERROR)
        return ToolResult(
            success=False,
            errors=[f"Unknown tool: {tool_name}"],
            source="router",
            latency_ms=0,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )
    if not tool_registry.is_allowed(tool_name, agent_id) and agent_id != "system":
        span_manager.end(tspan, status=SpanStatus.ERROR)
        return ToolResult(
            success=False,
            errors=[f"Agent {agent_id} not allowed to use {tool_name}"],
            source="router",
            latency_ms=0,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )

    if cap.side_effect_level >= 2:
        proposal = ActionProposal(
            task_id=correlation_id,
            agent=agent_id,
            action=tool_name,
            side_effect_level="EXECUTE_SAFE" if cap.side_effect_level == 2 else "EXECUTE_CRITICAL",
            impact_summary=f"Execute {tool_name} with params {params}",
        )
        decision = policy_engine.evaluate(proposal)
        if decision == PolicyDecision.ESCALATE:
            span_manager.end(tspan, status=SpanStatus.OK)
            return ToolResult(
                success=False,
                errors=["WAITING_APPROVAL"],
                data={"proposal": proposal.model_dump()},
                source="policy",
                latency_ms=0,
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

    if tool_name in CACHEABLE:
        cached = await cache_get(tool_name, params)
        if cached:
            span_manager.end(tspan, status=SpanStatus.OK)
            return ToolResult(
                success=True,
                data=cached,
                source="cache",
                latency_ms=0,
                cached=True,
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        span_manager.end(tspan, status=SpanStatus.ERROR)
        return ToolResult(
            success=False,
            errors=[f"No handler for {tool_name}"],
            source="router",
            latency_ms=0,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )

    source = "github_mcp" if tool_name in {"list_github_prs", "get_repo_health"} else "stub"
    result = await normalize_tool_call(tool_name, correlation_id, source, handler, **params)

    if result.success and tool_name in CACHEABLE and result.data:
        await cache_set(tool_name, params, result.data)

    span_manager.end(
        tspan,
        status=SpanStatus.OK if result.success else SpanStatus.ERROR,
        metadata={"latency_ms": result.latency_ms, "session_id": session_id or ""},
    )
    return result
