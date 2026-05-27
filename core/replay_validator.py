"""Replay validation via CanonicalReplayOutcome and frozen re-orchestration."""

from __future__ import annotations

import hashlib
from typing import Any

from core.persistence import (
    get_decisions_by_correlation,
    get_effects_by_correlation,
    get_replay_baseline,
    get_replay_snapshots,
)
from core.governance_store import list_approvals_by_correlation
from core.runtime_session import MemoryConnection
from schemas.replay import CanonicalReplayOutcome, outcome_fingerprint
from schemas.runtime import RuntimeState


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


async def reorchestrate_frozen_outcome(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
) -> CanonicalReplayOutcome:
    """Rebuild outcome from persisted snapshots (frozen tool outputs, no live tools)."""
    snapshots = await get_replay_snapshots(session_id, conn=conn)
    tool_sequence: list[str] = []
    final_state = RuntimeState.COMPLETED.value

    for snap in snapshots:
        if snap.get("runtime_state"):
            final_state = snap["runtime_state"]
        for tr in snap.get("tool_results", []):
            if isinstance(tr, dict) and tr.get("tool_name"):
                tool_sequence.append(tr["tool_name"])

    decisions = await get_decisions_by_correlation(correlation_id, conn=conn)
    effects = await get_effects_by_correlation(correlation_id, conn=conn)
    approvals_list: list[str] = []
    read_conn = conn
    if read_conn is None:
        from core.config import settings
        from core.persistence import get_pool

        if settings.use_in_memory_store:
            from core.runtime_session import MemoryConnection

            read_conn = MemoryConnection()
        else:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as c:
                    for a in await list_approvals_by_correlation(c, correlation_id):
                        approvals_list.append(a.id)
                read_conn = None
    if read_conn is not None:
        for a in await list_approvals_by_correlation(read_conn, correlation_id):
            approvals_list.append(a.id)

    return CanonicalReplayOutcome(
        final_runtime_state=final_state,
        tool_sequence=tool_sequence,
        decision_sequence=[d.id for d in decisions],
        side_effects=[e.id for e in effects],
        approvals=sorted(approvals_list),
    )


async def build_canonical_outcome(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
    final_runtime_state: str | None = None,
) -> CanonicalReplayOutcome:
    return await reorchestrate_frozen_outcome(session_id, correlation_id, conn=conn)


async def validate_frozen_replay(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
) -> tuple[bool, str, str | None]:
    """Re-orchestrate from frozen snapshots and compare to persisted baseline."""
    outcome = await reorchestrate_frozen_outcome(session_id, correlation_id, conn=conn)
    fp = outcome_fingerprint(outcome)
    baseline = await get_replay_baseline(session_id, conn=conn)
    if baseline is None:
        return False, fp, None
    return fp == baseline, fp, baseline
