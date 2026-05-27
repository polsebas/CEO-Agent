"""Context window manager — L1-L5 layers with budget caps."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.canonical import stable_hash
from core.context_lifecycle import context_lifecycle
from schemas.context import ContextFingerprint
from schemas.decisions import DecisionRecord
from schemas.runtime import ContextLayer
from schemas.world import WorldState


class ContextBundle(BaseModel):
    session_id: str
    task_id: str
    layers: dict[ContextLayer, str] = Field(default_factory=dict)
    estimated_tokens: int = 0
    fingerprint: ContextFingerprint | None = None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ContextWindowManager(BaseModel):
    max_tokens: int = 8000
    compression_strategy: str = "selective"
    summarization_policy: str = "truncate_long_fields"
    memory_priority_rules: dict[str, int] = Field(
        default_factory=lambda: {
            ContextLayer.L1_ACTIVE_TASK.value: 100,
            ContextLayer.L2_WORLD_STATE.value: 90,
            ContextLayer.L3_RECENT_DECISIONS.value: 70,
            ContextLayer.L4_LONG_TERM.value: 50,
            ContextLayer.L5_ARCHIVED.value: 30,
        }
    )
    eviction_strategy: str = "priority"

    def build_context(
        self,
        session_id: str,
        task_id: str,
        *,
        active_task: str,
        world_state: WorldState,
        recent_decisions: list[DecisionRecord] | None = None,
        long_term: str | None = None,
        archived: str | None = None,
        extra_layers: list[ContextLayer] | None = None,
    ) -> ContextBundle:
        context_lifecycle.register_session(session_id)
        bundle = ContextBundle(session_id=session_id, task_id=task_id)
        budget = self.max_tokens

        l1 = f"Active Task: {active_task}"
        bundle.layers[ContextLayer.L1_ACTIVE_TASK] = l1
        budget -= _estimate_tokens(l1)

        l2 = world_state.model_dump_json()
        if _estimate_tokens(l2) > budget:
            l2 = l2[: budget * 4]
        bundle.layers[ContextLayer.L2_WORLD_STATE] = l2
        budget -= _estimate_tokens(l2)

        requested = set(extra_layers or [])
        if recent_decisions and (ContextLayer.L3_RECENT_DECISIONS in requested or budget > 500):
            l3 = "\n".join(d.reasoning_summary for d in recent_decisions[-5:])
            if _estimate_tokens(l3) <= budget:
                bundle.layers[ContextLayer.L3_RECENT_DECISIONS] = l3
                budget -= _estimate_tokens(l3)

        if long_term and ContextLayer.L4_LONG_TERM in requested and budget > 300:
            bundle.layers[ContextLayer.L4_LONG_TERM] = long_term[: budget * 4]
            budget -= _estimate_tokens(bundle.layers[ContextLayer.L4_LONG_TERM])

        if archived and ContextLayer.L5_ARCHIVED in requested and budget > 200:
            bundle.layers[ContextLayer.L5_ARCHIVED] = archived[: budget * 4]

        used = self.max_tokens - max(0, budget)
        bundle.estimated_tokens = used
        sources = [layer.value for layer in bundle.layers]
        fp = ContextFingerprint(
            context_hash=stable_hash({k.value: v for k, v in bundle.layers.items()}),
            retrieval_sources=sources,
            retrieval_scores={s: float(self.memory_priority_rules.get(s, 50)) for s in sources},
            token_utilization=used / self.max_tokens if self.max_tokens else 0.0,
            compression_ratio=used / max(_estimate_tokens(active_task + l2), 1),
            compression_strategy=self.compression_strategy,
        )
        if context_lifecycle.should_summarize(fp):
            layers_str = {k.value: v for k, v in bundle.layers.items()}
            new_layers, entry = context_lifecycle.summarize_old_context(layers_str)
            bundle.layers = {ContextLayer(k): v for k, v in new_layers.items()}
            fp = context_lifecycle.enrich_fingerprint(
                fp,
                session_id=session_id,
                compression_strategy="deterministic_summarize",
                provenance_entry=entry,
            )
        else:
            fp = context_lifecycle.enrich_fingerprint(
                fp,
                session_id=session_id,
                compression_strategy=self.compression_strategy,
            )
        bundle.fingerprint = fp
        return bundle

    def within_budget(self, bundle: ContextBundle, memory_budget: int) -> bool:
        if bundle.fingerprint and bundle.fingerprint.token_utilization > 1.0:
            return False
        return bundle.estimated_tokens <= memory_budget

    def to_prompt(self, bundle: ContextBundle) -> str:
        parts = []
        for layer in ContextLayer:
            if layer in bundle.layers:
                parts.append(f"[{layer.value}]\n{bundle.layers[layer]}")
        return "\n\n".join(parts)
