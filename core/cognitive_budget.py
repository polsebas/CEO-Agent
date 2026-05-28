"""Map AdaptivePolicy to CognitiveBudget."""

from __future__ import annotations

from core.adaptive_policy import BASE_MEMORY_BUDGET
from schemas.adaptive import AdaptivePolicy
from schemas.runtime import CognitiveBudget


def adaptive_policy_to_budget(policy: AdaptivePolicy, *, base_memory: int = BASE_MEMORY_BUDGET) -> CognitiveBudget:
    memory = int(base_memory * policy.context_budget_ratio)
    return CognitiveBudget(
        memory_budget=max(1000, memory),
        max_retries=policy.max_retry_depth,
        force_deterministic=policy.deterministic_mode,
        tool_budget=min(5, policy.tool_parallelism_limit),
    )
