"""Replay analytics — drift and confidence."""

from __future__ import annotations

from typing import Any

from core.persistence import get_replay_baseline_meta, get_replay_snapshots
from core.replay_diff import diff_canonical_outcomes
from core.replay_validator import validate_frozen_replay
from core.replay_version import ORCHESTRATOR_VERSION
from schemas.diagnostics import ReplayAnalytics
from schemas.runtime import ReplayMode


async def analyze_replay(
    session_id: str,
    correlation_id: str,
    *,
    mode: ReplayMode = ReplayMode.FROZEN,
    conn: Any | None = None,
) -> ReplayAnalytics:
    ok, fp, baseline = await validate_frozen_replay(session_id, correlation_id, conn=conn)
    replay_confidence = 1.0 if ok else 0.0
    drift_severity = 0.0 if ok else 1.0
    tool_divergence = 0.0
    context_divergence = 0.0
    drift_fields: list[str] = []
    outcome_match = ok

    if mode == ReplayMode.LIVE:
        from core.live_replay_adapter import live_replay_adapter
        from core.replay_validator import reorchestrate_frozen_outcome

        expected = await reorchestrate_frozen_outcome(session_id, correlation_id, conn=conn)
        live = await live_replay_adapter.run_live_outcome(session_id, correlation_id, conn=conn)
        diff = diff_canonical_outcomes(expected, live)
        drift_fields = list(diff.keys())
        outcome_match = len(drift_fields) == 0
        if "tool_sequence" in drift_fields:
            tool_divergence = 1.0
        replay_confidence = 0.5 if outcome_match else 0.2
        drift_severity = len(drift_fields) / 5.0

    snaps = await get_replay_snapshots(session_id, conn=conn)
    hashes = [
        (snap.get("context_fingerprint") or {}).get("context_hash")
        for snap in snaps
        if snap.get("context_fingerprint")
    ]
    if len(set(h for h in hashes if h)) > 1:
        context_divergence = 0.5

    meta = await get_replay_baseline_meta(session_id, conn=conn)
    version = (meta or {}).get("orchestrator_version") or ORCHESTRATOR_VERSION

    return ReplayAnalytics(
        session_id=session_id,
        correlation_id=correlation_id,
        replay_confidence=replay_confidence,
        drift_severity=min(1.0, drift_severity),
        orchestration_version=version,
        context_divergence=context_divergence,
        tool_divergence=tool_divergence,
        outcome_match=outcome_match,
        drift_fields=drift_fields,
    )
