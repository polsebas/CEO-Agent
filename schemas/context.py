"""Context reliability models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextFingerprint(BaseModel):
    context_hash: str
    retrieval_sources: list[str] = Field(default_factory=list)
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    token_utilization: float = 0.0
    compression_ratio: float = 1.0
    context_age_seconds: int = 0
    provenance_chain: list[str] = Field(default_factory=list)
    compression_strategy: str | None = None
