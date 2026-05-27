"""Replay validation via FrozenReplayExecutor and CanonicalReplayOutcome."""

from __future__ import annotations

import hashlib
from typing import Any

from core.frozen_replay_executor import frozen_replay_executor
from core.persistence import get_replay_baseline, get_replay_baseline_meta
from core.replay_errors import ReplayIntegrityError, ReplayVersionMismatchError
from schemas.replay import CanonicalReplayOutcome, outcome_fingerprint


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


async def reorchestrate_frozen_outcome(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
) -> CanonicalReplayOutcome:
    """Frozen execution replay — delegates to FrozenReplayExecutor."""
    return await frozen_replay_executor.run_from_session(session_id, correlation_id, conn=conn)


def replay_confidence_from_baseline(outcome_fp: str, baseline_fp: str | None) -> float:
    """Derive replay confidence after baseline is available in the same close TX."""
    if baseline_fp is None:
        return 1.0
    return 1.0 if outcome_fp == baseline_fp else 0.0


async def build_canonical_outcome(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
    final_runtime_state: str | None = None,
) -> CanonicalReplayOutcome:
    outcome = await reorchestrate_frozen_outcome(session_id, correlation_id, conn=conn)
    if final_runtime_state is not None:
        return outcome.model_copy(update={"final_runtime_state": final_runtime_state})
    return outcome


async def validate_frozen_replay(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
) -> tuple[bool, str, str | None]:
    """Replay session and compare fingerprint to persisted baseline."""
    baseline = await get_replay_baseline(session_id, conn=conn)
    if baseline is None:
        return False, "", None

    meta = await get_replay_baseline_meta(session_id, conn=conn) or {}
    stored_version = meta.get("orchestrator_version")
    if stored_version and stored_version not in (
        frozen_replay_executor.ORCHESTRATOR_VERSION,
        "rrm15-legacy",
    ):
        return False, "", baseline

    try:
        outcome = await reorchestrate_frozen_outcome(session_id, correlation_id, conn=conn)
    except (ReplayIntegrityError, ReplayVersionMismatchError):
        return False, "", baseline

    fp = outcome_fingerprint(outcome)
    return fp == baseline, fp, baseline
