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


tool_registry = build_vs_registry()
