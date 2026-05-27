"""Canonical replay outcome models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.canonical import stable_hash


class CanonicalReplayOutcome(BaseModel):
    final_runtime_state: str
    tool_sequence: list[str] = Field(default_factory=list)
    decision_sequence: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)


def outcome_fingerprint(outcome: CanonicalReplayOutcome) -> str:
    return stable_hash(outcome.model_dump(mode="json"))
