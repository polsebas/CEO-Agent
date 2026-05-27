"""Build unified session diagnostics snapshot."""

from __future__ import annotations

from typing import Any

from core.persistence import (
    get_replay_baseline_meta,
    get_replay_snapshots,
    query_cognitive_telemetry,
    query_execution_spans,
    query_runtime_health,
)
from core.intelligence_store import get_anomalies
from schemas.diagnostics import SessionDiagnostics
from schemas.spans import SpanType


async def build_session_diagnostics(
    session_id: str,
    correlation_id: str,
    *,
    conn: Any | None = None,
) -> SessionDiagnostics:
    from core.config import settings
    from core.runtime_session import MemoryConnection

    spans = await query_execution_spans(session_id, correlation_id=correlation_id, conn=conn)
    telemetry = await query_cognitive_telemetry(session_id, correlation_id=correlation_id, conn=conn)
    health_rows = await query_runtime_health(session_id, conn=conn)
    health = health_rows[-1] if health_rows else None

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        anomalies = get_anomalies(session_id)
    else:
        from schemas.runtime_health import RuntimeAnomaly

        anomalies = []
        if conn is not None:
            rows = await conn.fetch(
                "SELECT data FROM runtime_anomalies WHERE session_id = $1 ORDER BY detected_at ASC",
                session_id,
            )
            import json

            for r in rows:
                data = r["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                anomalies.append(RuntimeAnomaly.model_validate(data))

    snaps = await get_replay_snapshots(session_id, conn=conn)
    baseline = await get_replay_baseline_meta(session_id, conn=conn)

    span_by_type: dict[str, int] = {}
    for s in spans:
        span_by_type[s.span_type.value] = span_by_type.get(s.span_type.value, 0) + 1

    return SessionDiagnostics(
        session_id=session_id,
        correlation_id=correlation_id,
        runtime_health=health,
        span_summary={
            "total": len(spans),
            "by_type": span_by_type,
            "orphans": sum(
                1
                for s in spans
                if s.parent_span_id
                and s.parent_span_id not in {x.span_id for x in spans}
                and s.span_type != SpanType.ORCHESTRATION
            ),
        },
        telemetry_summary={
            "records": len(telemetry),
            "total_tokens": sum(t.token_estimate for t in telemetry),
            "avg_context_pressure": (
                sum(t.context_pressure for t in telemetry) / len(telemetry) if telemetry else 0.0
            ),
            "total_retries": sum(t.retry_count for t in telemetry),
        },
        replay_summary={
            "snapshot_count": len(snaps),
            "baseline": baseline,
        },
        context_summary={
            "fingerprints": [
                snap.get("context_fingerprint")
                for snap in snaps
                if snap.get("context_fingerprint")
            ],
        },
        anomaly_events=anomalies,
    )
