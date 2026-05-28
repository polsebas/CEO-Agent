"""Deterministic context prioritization (RRM3-C1)."""

from __future__ import annotations

from schemas.context import ContextPriorityScore
from schemas.runtime import ContextLayer

LAYER_BASE_PRIORITY: dict[str, float] = {
    ContextLayer.L1_ACTIVE_TASK.value: 1.0,
    ContextLayer.L2_WORLD_STATE.value: 0.9,
    ContextLayer.L3_RECENT_DECISIONS.value: 0.7,
    ContextLayer.L4_LONG_TERM.value: 0.4,
    ContextLayer.L5_ARCHIVED.value: 0.2,
}

GOVERNANCE_SOURCES = {"governance", "replay", "policy", "approval"}


def score_layer(
    source_id: str,
    *,
    token_utilization: float = 0.0,
    session_age_seconds: int = 0,
    replay_relevance: float = 1.0,
) -> ContextPriorityScore:
    base = LAYER_BASE_PRIORITY.get(source_id, 0.5)
    if any(g in source_id.lower() for g in GOVERNANCE_SOURCES):
        operational = 1.0
    else:
        operational = base
    freshness = max(0.1, 1.0 - min(1.0, session_age_seconds / 7200.0))
    relevance = max(0.2, 1.0 - token_utilization * 0.3)
    return ContextPriorityScore(
        source_id=source_id,
        relevance_score=round(relevance, 4),
        freshness_score=round(freshness, 4),
        replay_relevance=round(replay_relevance, 4),
        operational_priority=round(operational, 4),
    )


def select_layers(
    layers: dict[str, str],
    *,
    memory_budget: int,
    estimated_tokens: int,
    token_utilization: float,
    session_age_seconds: int = 0,
) -> dict[str, str]:
    """Drop lowest-priority layers until within budget (deterministic)."""
    if estimated_tokens <= memory_budget:
        return layers

    def _estimate_tokens(layer_map: dict[str, str]) -> int:
        return max(1, sum(len(v) for v in layer_map.values()) // 4)

    scored = [
        (score_layer(k, token_utilization=token_utilization, session_age_seconds=session_age_seconds), k, v)
        for k, v in layers.items()
    ]
    scored.sort(key=lambda x: x[0].composite)
    result = dict(layers)
    protected = {ContextLayer.L1_ACTIVE_TASK.value, ContextLayer.L2_WORLD_STATE.value}
    for _score, key, _val in scored:
        if key in protected or key not in result:
            continue
        result.pop(key, None)
        if _estimate_tokens(result) <= memory_budget:
            break
    return result
