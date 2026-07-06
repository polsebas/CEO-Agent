"""Tool capability registry."""

from __future__ import annotations

from pydantic import BaseModel

from schemas.runtime import RetryPolicy


class ToolCapability(BaseModel):
    name: str
    action_class: str
    allowed_agents: list[str]
    side_effect_level: int
    timeout_seconds: float = 3.0
    retry_policy: RetryPolicy = RetryPolicy()


class ToolCapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, ToolCapability] = {}

    def register(self, capability: ToolCapability) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> ToolCapability | None:
        return self._capabilities.get(name)

    def agents_for_capability(self, action_class: str, domain: str = "") -> list[str]:
        return [
            agent
            for cap in self._capabilities.values()
            if cap.action_class == action_class and (not domain or domain in cap.name)
            for agent in cap.allowed_agents
        ]

    def is_allowed(self, tool_name: str, agent_id: str) -> bool:
        cap = self.get(tool_name)
        return cap is not None and agent_id in cap.allowed_agents

    def all_tools(self) -> list[ToolCapability]:
        return list(self._capabilities.values())


def build_vs_registry() -> ToolCapabilityRegistry:
    registry = ToolCapabilityRegistry()
    vs_tools = [
        ("list_github_prs", "READ", ["cto"], 0),
        ("get_repo_health", "READ", ["cto"], 0),
        ("analyze_incidents", "ANALYZE", ["cto"], 0),
        ("prioritize_bugs", "PLAN", ["cto"], 1),
        ("read_kpi_dashboard", "READ", ["ceo"], 0),
        ("create_initiative", "PLAN", ["ceo"], 1),
        ("escalate_to_human", "PLAN", ["ceo"], 1),
        ("get_cashflow_summary", "READ", ["cfo"], 0),
        ("calculate_runway", "ANALYZE", ["cfo"], 0),
        ("detect_blockers", "ANALYZE", ["coo"], 0),
        ("list_active_tasks", "READ", ["coo"], 0),
        ("get_analytics_summary", "READ", ["cmo"], 0),
        ("propose_campaign", "PLAN", ["cmo"], 1),
    ]
    for name, action_class, agents, level in vs_tools:
        registry.register(
            ToolCapability(
                name=name,
                action_class=action_class,
                allowed_agents=agents,
                side_effect_level=level,
            )
        )
    return registry


def build_facilrentacar_registry() -> ToolCapabilityRegistry:
    registry = ToolCapabilityRegistry()
    read_tools = [
        ("get_reservation_detail", "READ", ["cfo", "ceo"], 0),
        ("get_compensation_policy", "READ", ["cfo", "ceo"], 0),
        ("get_client_history", "READ", ["cfo", "ceo"], 0),
        ("get_cancellation_policy", "READ", ["cfo", "ceo"], 0),
        ("get_fleet_occupancy", "READ", ["coo", "cfo", "ceo"], 0),
        ("get_current_rates", "READ", ["cfo", "ceo"], 0),
        ("get_market_rates", "READ", ["cfo", "ceo"], 0),
        ("get_branch_status", "READ", ["coo", "ceo"], 0),
        ("get_pending_reservations_by_branch", "READ", ["coo", "ceo"], 0),
    ]
    mutate_tools = [
        ("apply_reservation_discount", "EXECUTE", ["ceo", "system"], 3),
        ("execute_cancellation_override", "EXECUTE", ["ceo", "system"], 3),
        ("publish_rate_adjustment", "EXECUTE", ["ceo", "system"], 3),
        ("activate_vehicles", "EXECUTE", ["ceo", "system"], 3),
    ]
    for name, action_class, agents, level in read_tools + mutate_tools:
        registry.register(
            ToolCapability(
                name=name,
                action_class=action_class,
                allowed_agents=agents,
                side_effect_level=level,
            )
        )
    return registry


def build_merged_registry() -> ToolCapabilityRegistry:
    merged = build_vs_registry()
    for cap in build_facilrentacar_registry().all_tools():
        merged.register(cap)
    return merged


tool_registry = build_merged_registry()
