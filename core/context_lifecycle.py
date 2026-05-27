"""Context lifecycle — aging, compression, budget enforcement."""

from __future__ import annotations

import time
from typing import Any

from core.canonical import stable_hash
from schemas.context import ContextFingerprint


class ContextLifecycleManager:
    def __init__(self) -> None:
        self._session_started: dict[str, float] = {}

    def register_session(self, session_id: str) -> None:
        if session_id not in self._session_started:
            self._session_started[session_id] = time.time()

    def context_age_seconds(self, session_id: str) -> int:
        started = self._session_started.get(session_id, time.time())
        return int(time.time() - started)

    def enrich_fingerprint(
        self,
        fp: ContextFingerprint,
        *,
        session_id: str,
        compression_strategy: str = "selective",
        provenance_entry: str | None = None,
    ) -> ContextFingerprint:
        age = self.context_age_seconds(session_id)
        chain = list(fp.provenance_chain)
        if provenance_entry and provenance_entry not in chain:
            chain.append(provenance_entry)
        return fp.model_copy(
            update={
                "context_age_seconds": age,
                "compression_strategy": compression_strategy,
                "provenance_chain": chain,
            }
        )

    def context_pressure(self, fp: ContextFingerprint) -> float:
        return fp.token_utilization

    def should_summarize(self, fp: ContextFingerprint) -> bool:
        return fp.token_utilization > 0.9

    def summarize_old_context(self, layers: dict[str, str]) -> tuple[dict[str, str], str]:
        """Deterministic truncation — no semantic memory."""
        summarized: dict[str, str] = {}
        for key, value in layers.items():
            if len(value) > 400:
                summarized[key] = value[:400] + f"...[truncated:{stable_hash(value)[:8]}]"
            else:
                summarized[key] = value
        lineage_entry = f"summarize:{stable_hash(summarized)}"
        return summarized, lineage_entry

    def enforce_budget(self, token_utilization: float, memory_budget: int, estimated_tokens: int) -> bool:
        if token_utilization > 1.0:
            return False
        return estimated_tokens <= memory_budget


context_lifecycle = ContextLifecycleManager()
