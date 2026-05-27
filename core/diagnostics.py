"""Read-only diagnostics service — no orchestrator calls."""

from __future__ import annotations

from typing import Any

from core.persistence import (
    query_cognitive_telemetry,
    query_execution_spans,
    query_runtime_health,
    query_session_diagnostics_row,
)
from core.intelligence_store import get_lineage
from core.replay_analytics import analyze_replay
from core.session_diagnostics import build_session_diagnostics
from schemas.diagnostics import ReplayAnalytics, SessionDiagnostics
from schemas.runtime import ReplayMode


class DiagnosticsService:
    async def get_health(self, session_id: str, *, conn: Any | None = None):
        rows = await query_runtime_health(session_id, conn=conn)
        return rows[-1].model_dump() if rows else None

    async def get_spans(self, session_id: str, *, correlation_id: str | None = None, conn: Any | None = None):
        spans = await query_execution_spans(session_id, correlation_id=correlation_id, conn=conn)
        return _span_tree(spans)

    async def get_telemetry(self, session_id: str, *, correlation_id: str | None = None, conn: Any | None = None):
        rows = await query_cognitive_telemetry(session_id, correlation_id=correlation_id, conn=conn)
        return [r.model_dump() for r in rows]

    async def get_context(self, session_id: str, *, conn: Any | None = None):
        from core.config import settings
        from core.persistence import get_replay_snapshots
        from core.runtime_session import MemoryConnection

        snaps = await get_replay_snapshots(session_id, conn=conn)
        lineage = []
        if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
            lineage = [p.model_dump() for p in get_lineage(session_id)]
        elif conn is not None:
            import json

            from schemas.cognition import PromptLineage

            rows = await conn.fetch(
                "SELECT data FROM prompt_lineage WHERE session_id = $1",
                session_id,
            )
            for r in rows:
                data = r["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                lineage.append(PromptLineage.model_validate(data).model_dump())

        return {
            "session_id": session_id,
            "fingerprints": [s.get("context_fingerprint") for s in snaps if s.get("context_fingerprint")],
            "lineage": lineage,
        }

    async def get_diagnostics(
        self,
        session_id: str,
        correlation_id: str,
        *,
        conn: Any | None = None,
    ) -> SessionDiagnostics:
        cached = await query_session_diagnostics_row(session_id, conn=conn)
        if cached:
            return cached
        return await build_session_diagnostics(session_id, correlation_id, conn=conn)

    async def get_replay_analysis(
        self,
        session_id: str,
        correlation_id: str,
        *,
        mode: ReplayMode = ReplayMode.FROZEN,
        conn: Any | None = None,
    ) -> ReplayAnalytics:
        return await analyze_replay(session_id, correlation_id, mode=mode, conn=conn)


def _span_tree(spans: list) -> dict:
    by_id = {s.span_id: s.model_dump() for s in spans}
    roots = [s for s in spans if not s.parent_span_id or s.span_type.value == "orchestration"]
    return {
        "spans": list(by_id.values()),
        "roots": [r.span_id for r in roots],
        "total": len(spans),
    }


diagnostics_service = DiagnosticsService()
