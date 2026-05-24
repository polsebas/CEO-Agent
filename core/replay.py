"""Replay engine — frozen uses historical snapshots only."""

from __future__ import annotations

from schemas.runtime import ReplayMode, ReplaySession, ReplaySnapshot, RuntimeState
from core.persistence import get_replay_snapshots


class ReplayEngine:
    async def replay_session(
        self,
        session_id: str,
        correlation_id: str,
        mode: ReplayMode = ReplayMode.FROZEN,
    ) -> ReplaySession:
        snapshots_raw = await get_replay_snapshots(session_id)

        if not snapshots_raw:
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

        if mode == ReplayMode.FROZEN:
            for i, snap in enumerate(snapshots_raw):
                tool_outputs = {}
                for tr in snap.get("tool_results", []):
                    if isinstance(tr, dict) and "tool_name" in tr:
                        tool_outputs[tr["tool_name"]] = tr
                    elif isinstance(tr, dict):
                        tool_outputs[f"tool_{i}"] = tr
                legacy = snap.get("tool_outputs", {})
                tool_outputs.update(legacy)

                session.snapshots.append(
                    ReplaySnapshot(
                        step=i,
                        runtime_state=RuntimeState(snap.get("runtime_state", "completed")),
                        prompt_hash=str(hash(snap.get("prompt", "")))[:16],
                        tool_outputs=tool_outputs,
                        world_state_version=snap.get("world_state_version", ws_version),
                        timestamp=snap.get("timestamp") or __import__("datetime").datetime.utcnow(),
                    )
                )
            session.outcome_match = len(snapshots_raw) > 0 and all(
                s.get("response") or s.get("tool_results") for s in snapshots_raw
            )
            return session

        last = snapshots_raw[-1]
        session.snapshots.append(
            ReplaySnapshot(
                step=0,
                runtime_state=RuntimeState(last.get("runtime_state", "completed")),
                prompt_hash="live_from_last_snapshot",
                tool_outputs={
                    tr.get("tool_name", f"tool_{idx}"): tr
                    for idx, tr in enumerate(last.get("tool_results", []))
                    if isinstance(tr, dict)
                },
                world_state_version=last.get("world_state_version", ws_version),
                timestamp=__import__("datetime").datetime.utcnow(),
            )
        )
        session.outcome_match = bool(last.get("response"))
        return session


replay_engine = ReplayEngine()
