"""Replay engine — frozen baseline compare; live drift detection."""

from __future__ import annotations

from datetime import datetime, timezone

from core.live_replay_adapter import live_replay_adapter
from core.replay_diff import diff_canonical_outcomes
from core.replay_validator import prompt_hash, reorchestrate_frozen_outcome, validate_frozen_replay
from core.persistence import get_replay_snapshots
from schemas.replay import outcome_fingerprint
from schemas.runtime import ReplayMode, ReplaySession, ReplaySnapshot, RuntimeState


class ReplayEngine:
    async def replay_session(
        self,
        session_id: str,
        correlation_id: str,
        mode: ReplayMode = ReplayMode.FROZEN,
    ) -> ReplaySession:
        from core.spans import span_manager
        from schemas.spans import SpanStatus, SpanType

        span_manager.begin_session(session_id=session_id, correlation_id=correlation_id)
        rspan = span_manager.start(SpanType.REPLAY, metadata={"mode": mode.value})
        snapshots_raw = await get_replay_snapshots(session_id)

        if not snapshots_raw:
            span_manager.end(rspan, status=SpanStatus.ERROR)
            return ReplaySession(
                session_id=session_id,
                correlation_id=correlation_id,
                mode=mode,
                world_state_snapshot={},
                snapshots=[],
                outcome_match=False,
            )

        first = snapshots_raw[0]
        ws_version = first.get("world_state_version", 0)
        session = ReplaySession(
            session_id=session_id,
            correlation_id=correlation_id,
            mode=mode,
            world_state_snapshot={"version": ws_version, "source": "historical_snapshot"},
            snapshots=[],
        )

        for i, snap in enumerate(snapshots_raw):
            tool_outputs = {}
            for tr in snap.get("tool_results", []):
                if isinstance(tr, dict) and "tool_name" in tr:
                    tool_outputs[tr["tool_name"]] = tr
            legacy = snap.get("tool_outputs", {})
            tool_outputs.update(legacy)

            session.snapshots.append(
                ReplaySnapshot(
                    step=i,
                    runtime_state=RuntimeState(snap.get("runtime_state", "completed")),
                    prompt_hash=prompt_hash(snap.get("prompt", "")),
                    tool_outputs=tool_outputs,
                    world_state_version=snap.get("world_state_version", ws_version),
                    timestamp=snap.get("timestamp") or datetime.now(timezone.utc),
                )
            )

        if mode == ReplayMode.FROZEN:
            match, fp, baseline = await validate_frozen_replay(session_id, correlation_id)
            session.outcome_match = match and baseline is not None
            session.world_state_snapshot["outcome_fingerprint"] = fp
            session.world_state_snapshot["baseline_fingerprint"] = baseline
            span_manager.end(rspan, status=SpanStatus.OK if session.outcome_match else SpanStatus.ERROR)
            return session

        baseline_outcome = await reorchestrate_frozen_outcome(session_id, correlation_id)
        live_outcome = await live_replay_adapter.run_live_outcome(
            session_id, correlation_id
        )
        drift = diff_canonical_outcomes(baseline_outcome, live_outcome)
        session.world_state_snapshot["expected_fingerprint"] = outcome_fingerprint(
            baseline_outcome
        )
        session.world_state_snapshot["live_fingerprint"] = outcome_fingerprint(live_outcome)
        session.world_state_snapshot["replay_source"] = "live_tool_adapter"
        session.outcome_match = len(drift) == 0
        session.world_state_snapshot["drift_fields"] = list(drift.keys())
        span_manager.end(rspan, status=SpanStatus.OK if session.outcome_match else SpanStatus.ERROR)
        return session


replay_engine = ReplayEngine()
