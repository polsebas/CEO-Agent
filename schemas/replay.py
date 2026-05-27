"""Canonical replay outcome models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.canonical import stable_hash


class PersistedRuntimeTransition(BaseModel):
    correlation_id: str
    session_id: str
    from_state: str
    to_state: str


class ReplayStepBundle(BaseModel):
    step: int
    runtime_state: str
    tool_results: list[dict] = Field(default_factory=list)
    prompt: str = ""
    response: dict = Field(default_factory=dict)
    world_state_version: int = 0
    delegation_messages: list[dict] = Field(default_factory=list)


class SnapshotBundle(BaseModel):
    session_id: str
    correlation_id: str
    orchestrator_version: str
    world_state_version: int = 0
    policy_snapshot: dict = Field(default_factory=dict)
    steps: list[ReplayStepBundle] = Field(default_factory=list)
    transitions: list[PersistedRuntimeTransition] = Field(default_factory=list)
    intent_tool: str | None = None


class CanonicalReplayOutcome(BaseModel):
    final_runtime_state: str
    tool_sequence: list[str] = Field(default_factory=list)
    decision_sequence: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)


def outcome_fingerprint(outcome: CanonicalReplayOutcome) -> str:
    return stable_hash(outcome.model_dump(mode="json"))
