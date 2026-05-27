"""Live replay — re-execute tools into a copied bundle (never mutates persisted snapshots)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Awaitable, Callable

from core.frozen_replay_executor import frozen_replay_executor
from schemas.replay import CanonicalReplayOutcome, ReplayStepBundle, SnapshotBundle
from schemas.tools import ToolResult
from tools.router import execute_tool

ToolExecutor = Callable[[str, str, str, dict | None], Awaitable[ToolResult]]

_CTO_TOOLS = frozenset({"get_repo_health", "list_github_prs", "analyze_incidents", "prioritize_bugs"})


def _default_agent_id(tool_name: str, frozen: dict) -> str:
    if frozen.get("agent_id"):
        return str(frozen["agent_id"])
    if tool_name in _CTO_TOOLS:
        return "cto"
    return "ceo"


class LiveToolReplayAdapter:
    """Re-run tools for drift detection; persisted snapshot store stays untouched."""

    def __init__(
        self,
        *,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self._execute = tool_executor or execute_tool

    async def build_live_bundle(
        self,
        session_id: str,
        correlation_id: str,
        *,
        conn: Any | None = None,
    ) -> SnapshotBundle:
        bundle = await frozen_replay_executor.load_bundle(
            session_id, correlation_id, conn=conn
        )
        live = bundle.model_copy(deep=True)
        await self._refresh_tool_results(live, correlation_id)
        return live

    async def run_live_outcome(
        self,
        session_id: str,
        correlation_id: str,
        *,
        conn: Any | None = None,
    ) -> CanonicalReplayOutcome:
        live_bundle = await self.build_live_bundle(
            session_id, correlation_id, conn=conn
        )
        return await frozen_replay_executor.run(live_bundle, conn=conn)

    async def _refresh_tool_results(
        self, bundle: SnapshotBundle, correlation_id: str
    ) -> None:
        if bundle.intent_tool and not bundle.steps:
            live = await self._execute(
                bundle.intent_tool,
                _default_agent_id(bundle.intent_tool, {}),
                correlation_id,
                None,
            )
            bundle.steps = [
                ReplayStepBundle(
                    step=0,
                    runtime_state="completed",
                    tool_results=[live.model_dump(mode="json")],
                    prompt=f"deterministic:{bundle.intent_tool}",
                )
            ]
            return

        for step in bundle.steps:
            refreshed: list[dict] = []
            for frozen_tr in step.tool_results:
                if not isinstance(frozen_tr, dict) or not frozen_tr.get("tool_name"):
                    refreshed.append(deepcopy(frozen_tr))
                    continue
                tool_name = frozen_tr["tool_name"]
                agent_id = _default_agent_id(tool_name, frozen_tr)
                params = frozen_tr.get("params")
                if params is not None and not isinstance(params, dict):
                    params = None
                live = await self._execute(tool_name, agent_id, correlation_id, params)
                refreshed.append(live.model_dump(mode="json"))
            step.tool_results = refreshed


live_replay_adapter = LiveToolReplayAdapter()
