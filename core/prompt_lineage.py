"""Prompt ancestry tracking."""

from __future__ import annotations

from schemas.cognition import PromptLineage
from schemas.context import ContextFingerprint


class PromptLineageTracker:
    def __init__(self) -> None:
        self._last_hash: dict[tuple[str, str], str] = {}

    def build(
        self,
        *,
        prompt: str,
        session_id: str,
        correlation_id: str,
        fingerprint: ContextFingerprint | None = None,
        compression_strategy: str | None = None,
    ) -> PromptLineage:
        from core.cognition_metrics import hash_prompt_material

        key = (session_id, correlation_id)
        parent = self._last_hash.get(key)
        ph = hash_prompt_material(prompt)
        lineage = PromptLineage(
            prompt_hash=ph,
            session_id=session_id,
            correlation_id=correlation_id,
            parent_prompt_hash=parent,
            derived_from_context_hash=fingerprint.context_hash if fingerprint else None,
            compression_strategy=compression_strategy or (
                fingerprint.compression_strategy if fingerprint else None
            ),
        )
        self._last_hash[key] = ph
        return lineage

    def reset_session(self, session_id: str) -> None:
        self._last_hash = {k: v for k, v in self._last_hash.items() if k[0] != session_id}


prompt_lineage_tracker = PromptLineageTracker()
