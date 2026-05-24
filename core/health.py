"""Agent health tracking with persistence — no mutable globals across workers."""

from __future__ import annotations

from schemas.health import AgentHealth


class AgentHealthRegistry:
    def __init__(self) -> None:
        self._cache: dict[str, AgentHealth] = {}

    async def get(self, agent_id: str) -> AgentHealth:
        if agent_id in self._cache:
            return self._cache[agent_id]
        from core.persistence import load_agent_health

        stored = await load_agent_health(agent_id)
        if stored:
            health = AgentHealth.model_validate(stored)
            self._cache[agent_id] = health
            return health
        health = AgentHealth(agent_id=agent_id)
        self._cache[agent_id] = health
        return health

    async def record_run(
        self,
        agent_id: str,
        *,
        success: bool,
        latency_ms: float,
        structured_failure: bool = False,
        policy_violation: bool = False,
        retries: int = 0,
    ) -> AgentHealth:
        health = await self.get(agent_id)
        health.record_run(success=success, latency_ms=latency_ms, structured_failure=structured_failure)
        if policy_violation:
            health.policy_violations += 1
        if retries:
            health.retries_per_run = (
                (health.retries_per_run * (health.total_runs - 1) + retries) / health.total_runs
            )
        from core.config import settings

        health.degraded_mode = health.success_rate < settings.degraded_success_threshold
        await self._persist(agent_id, health)
        return health

    async def is_degraded(self, agent_id: str) -> bool:
        return (await self.get(agent_id)).degraded_mode

    async def all_agents(self) -> dict[str, AgentHealth]:
        from core.persistence import load_all_agent_health

        stored = await load_all_agent_health()
        for agent_id, data in stored.items():
            self._cache[agent_id] = AgentHealth.model_validate(data)
        return dict(self._cache)

    async def _persist(self, agent_id: str, health: AgentHealth) -> None:
        from core.persistence import save_agent_health

        await save_agent_health(agent_id, health.model_dump(mode="json"))

    def _health_sync(self, agent_id: str) -> AgentHealth:
        """Sync access for hot paths — uses cache only."""
        if agent_id not in self._cache:
            self._cache[agent_id] = AgentHealth(agent_id=agent_id)
        return self._cache[agent_id]

    def record_run_sync(
        self,
        agent_id: str,
        *,
        success: bool,
        latency_ms: float,
    ) -> None:
        health = self._health_sync(agent_id)
        health.record_run(success=success, latency_ms=latency_ms)
        from core.config import settings

        health.degraded_mode = health.success_rate < settings.degraded_success_threshold

    def is_degraded_sync(self, agent_id: str) -> bool:
        return self._health_sync(agent_id).degraded_mode

    def clear(self) -> None:
        self._cache.clear()


agent_health_registry = AgentHealthRegistry()
