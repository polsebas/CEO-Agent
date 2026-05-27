"""Frozen replay — step-by-step runtime replay from persisted bundle (no live tools/LLM)."""

from __future__ import annotations

from typing import Any

from core.governance_store import list_approvals_by_correlation
from core.persistence import (
    get_decisions_by_correlation,
    get_effects_by_correlation,
    get_events_by_correlation,
    get_replay_baseline_meta,
    get_replay_snapshots,
    get_runtime_transitions,
)
from core.replay_errors import ReplayIntegrityError, ReplayVersionMismatchError
from core.replay_version import ORCHESTRATOR_VERSION
from core.runtime import InvalidStateTransition, RuntimeStateMachine
from schemas.replay import (
    CanonicalReplayOutcome,
    PersistedRuntimeTransition,
    ReplayStepBundle,
    SnapshotBundle,
)
from schemas.runtime import RuntimeState


class FrozenReplayExecutor:
    ORCHESTRATOR_VERSION = ORCHESTRATOR_VERSION

    async def load_bundle(
        self,
        session_id: str,
        correlation_id: str,
        *,
        conn: Any | None = None,
    ) -> SnapshotBundle:
        snapshots = await get_replay_snapshots(session_id, conn=conn)
        raw_transitions = await get_runtime_transitions(session_id, conn=conn)
        transitions = [
            PersistedRuntimeTransition(
                correlation_id=t.correlation_id if hasattr(t, "correlation_id") else t["correlation_id"],
                session_id=t.session_id if hasattr(t, "session_id") else t["session_id"],
                from_state=t.from_state if hasattr(t, "from_state") else t["from_state"],
                to_state=t.to_state if hasattr(t, "to_state") else t["to_state"],
            )
            for t in raw_transitions
        ]
        meta = await get_replay_baseline_meta(session_id, conn=conn)
        version = (meta or {}).get("orchestrator_version") or "rrm15-legacy"

        steps: list[ReplayStepBundle] = []
        world_version = 0
        for i, snap in enumerate(snapshots):
            world_version = snap.get("world_state_version", world_version)
            steps.append(
                ReplayStepBundle(
                    step=i,
                    runtime_state=snap.get("runtime_state", RuntimeState.COMPLETED.value),
                    tool_results=list(snap.get("tool_results") or []),
                    prompt=snap.get("prompt", ""),
                    response=dict(snap.get("response") or {}),
                    world_state_version=world_version,
                )
            )

        intent_tool: str | None = None
        events = await get_events_by_correlation(correlation_id, conn=conn)
        for event in events:
            if event.event_type == "founder.intent":
                payload = event.payload or {}
                intent_tool = payload.get("tool") or (
                    payload.get("message", "").split("deterministic:")[-1]
                    if "deterministic:" in str(payload.get("message", ""))
                    else None
                )

        policy_snapshot: dict = {}
        for event in events:
            if event.event_type == "decision.recorded":
                policies = (event.payload or {}).get("policies_applied") or []
                if policies:
                    policy_snapshot["policies_applied"] = policies
                break

        return SnapshotBundle(
            session_id=session_id,
            correlation_id=correlation_id,
            orchestrator_version=version,
            world_state_version=world_version,
            policy_snapshot=policy_snapshot,
            steps=steps,
            transitions=transitions,
            intent_tool=intent_tool,
        )

    async def run(
        self,
        bundle: SnapshotBundle,
        *,
        conn: Any | None = None,
    ) -> CanonicalReplayOutcome:
        if (
            bundle.orchestrator_version != "rrm15-legacy"
            and bundle.orchestrator_version != self.ORCHESTRATOR_VERSION
        ):
            raise ReplayVersionMismatchError(
                f"bundle version {bundle.orchestrator_version!r} != executor {self.ORCHESTRATOR_VERSION!r}"
            )

        if not bundle.transitions and not bundle.steps and not bundle.intent_tool:
            raise ReplayIntegrityError("No replay bundle data for session")

        sm = RuntimeStateMachine(
            correlation_id=bundle.correlation_id,
            session_id=bundle.session_id,
        )
        self._replay_transitions(sm, bundle.transitions)

        tool_sequence = self._collect_tool_sequence(bundle)
        self._verify_delegation_routing(bundle, tool_sequence)
        self._verify_step_runtime_states(sm, bundle)

        if sm.state != RuntimeState.COMPLETED:
            try:
                sm.complete()
            except InvalidStateTransition as exc:
                raise ReplayIntegrityError(
                    f"State machine could not complete after replay: {sm.state.value}"
                ) from exc

        decisions = await get_decisions_by_correlation(bundle.correlation_id, conn=conn)
        effects = await get_effects_by_correlation(bundle.correlation_id, conn=conn)
        approvals_list = await self._load_approvals(bundle.correlation_id, conn=conn)

        return CanonicalReplayOutcome(
            final_runtime_state=sm.state.value,
            tool_sequence=tool_sequence,
            decision_sequence=[d.id for d in decisions],
            side_effects=[e.id for e in effects],
            approvals=sorted(approvals_list),
        )

    async def run_from_session(
        self,
        session_id: str,
        correlation_id: str,
        *,
        conn: Any | None = None,
    ) -> CanonicalReplayOutcome:
        bundle = await self.load_bundle(session_id, correlation_id, conn=conn)
        return await self.run(bundle, conn=conn)

    def _replay_transitions(self, sm: RuntimeStateMachine, transitions: list) -> None:
        if not transitions:
            sm.start()
            return

        sm.start()
        for tr in transitions:
            from_state = tr.from_state
            to_state = tr.to_state
            if sm.state.value != from_state:
                raise ReplayIntegrityError(
                    f"Transition mismatch: expected from {from_state!r}, sm={sm.state.value!r}"
                )
            try:
                sm.transition(RuntimeState(to_state))
            except InvalidStateTransition as exc:
                raise ReplayIntegrityError(
                    f"Invalid replay transition {from_state!r} -> {to_state!r}"
                ) from exc

    def _collect_tool_sequence(self, bundle: SnapshotBundle) -> list[str]:
        sequence: list[str] = []
        for step in bundle.steps:
            for tr in step.tool_results:
                if isinstance(tr, dict) and tr.get("tool_name"):
                    sequence.append(tr["tool_name"])

        if not sequence and bundle.intent_tool:
            sequence.append(bundle.intent_tool)

        return sequence

    def _verify_delegation_routing(self, bundle: SnapshotBundle, tool_sequence: list[str]) -> None:
        for step in bundle.steps:
            delegations = step.response.get("delegations") or []
            if "cto" in delegations:
                cto_tools = {"get_repo_health", "list_github_prs", "analyze_incidents"}
                if not any(t in tool_sequence for t in cto_tools):
                    raise ReplayIntegrityError(
                        "CEO delegated to CTO but frozen tool sequence has no CTO tools"
                    )

    def _verify_step_runtime_states(
        self, sm: RuntimeStateMachine, bundle: SnapshotBundle
    ) -> None:
        if not bundle.steps:
            return
        last_step = bundle.steps[-1]
        if last_step.runtime_state != sm.state.value and sm.state == RuntimeState.COMPLETED:
            if last_step.runtime_state not in (RuntimeState.COMPLETED.value, RuntimeState.OBSERVING.value):
                raise ReplayIntegrityError(
                    f"Final snapshot state {last_step.runtime_state!r} "
                    f"inconsistent with SM {sm.state.value!r}"
                )

    async def _load_approvals(self, correlation_id: str, *, conn: Any | None) -> list[str]:
        if conn is not None:
            return [a.id for a in await list_approvals_by_correlation(conn, correlation_id)]

        from core.config import settings
        from core.persistence import get_pool
        from core.runtime_session import MemoryConnection

        if settings.use_in_memory_store:
            read_conn = MemoryConnection()
            return [a.id for a in await list_approvals_by_correlation(read_conn, correlation_id)]

        pool = await get_pool()
        if pool:
            async with pool.acquire() as c:
                return [a.id for a in await list_approvals_by_correlation(c, correlation_id)]
        return []


frozen_replay_executor = FrozenReplayExecutor()
