"""Context reliability models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextPriorityScore(BaseModel):
    source_id: str
    relevance_score: float = 1.0
    freshness_score: float = 1.0
    replay_relevance: float = 1.0
    operational_priority: float = 1.0

    @property
    def composite(self) -> float:
        return (
            self.relevance_score * 0.3
            + self.freshness_score * 0.2
            + self.replay_relevance * 0.25
            + self.operational_priority * 0.25
        )


class ContextFingerprint(BaseModel):
    context_hash: str
    retrieval_sources: list[str] = Field(default_factory=list)
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    token_utilization: float = 0.0
    compression_ratio: float = 1.0
    context_age_seconds: int = 0
    provenance_chain: list[str] = Field(default_factory=list)
    compression_strategy: str | None = None
