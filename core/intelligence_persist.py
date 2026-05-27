"""Persist RRM-2 intelligence entities (Postgres + in-memory)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.intelligence_store import (
    append_anomalies,
    append_lineage,
    append_spans,
    append_telemetry,
    replace_health,
    save_session_diagnostics,
)
from core.runtime_session import MemoryConnection


def apply_intelligence_memory(payload) -> None:
    if payload.execution_spans:
        append_spans(payload.execution_spans)
    if payload.cognitive_telemetry:
        append_telemetry(payload.cognitive_telemetry)
    if payload.runtime_health:
        replace_health(payload.runtime_health)
    if payload.prompt_lineage:
        append_lineage(payload.prompt_lineage)
    if payload.runtime_anomalies:
        append_anomalies(payload.runtime_anomalies)
    if payload.session_diagnostics:
        save_session_diagnostics(payload.session_diagnostics)


async def persist_intelligence_postgres(conn: Any, payload) -> None:
    now = datetime.now(timezone.utc)
    for span in payload.execution_spans or []:
        await conn.execute(
            """
            INSERT INTO execution_spans
            (span_id, trace_id, correlation_id, session_id, parent_span_id, span_type,
             runtime_state, started_at, completed_at, status, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
            ON CONFLICT (span_id) DO UPDATE SET
                completed_at = EXCLUDED.completed_at,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata
            """,
            span.span_id,
            span.trace_id,
            span.correlation_id,
            span.session_id,
            span.parent_span_id,
            span.span_type.value,
            span.runtime_state,
            span.started_at,
            span.completed_at,
            span.status.value,
            json.dumps(span.metadata),
        )
    for tel in payload.cognitive_telemetry or []:
        await conn.execute(
            """
            INSERT INTO cognitive_telemetry (correlation_id, session_id, agent_id, data, created_at)
            VALUES ($1,$2,$3,$4::jsonb,$5)
            """,
            tel.correlation_id,
            tel.session_id,
            tel.agent_id,
            tel.model_dump_json(),
            tel.created_at,
        )
    if payload.runtime_health:
        h = payload.runtime_health
        await conn.execute(
            """
            DELETE FROM runtime_health_snapshots
            WHERE session_id = $1 AND correlation_id = $2
            """,
            h.session_id,
            h.correlation_id,
        )
        await conn.execute(
            """
            INSERT INTO runtime_health_snapshots (session_id, correlation_id, data, generated_at)
            VALUES ($1,$2,$3::jsonb,$4)
            """,
            h.session_id,
            h.correlation_id,
            h.model_dump_json(),
            h.generated_at,
        )
    for pl in payload.prompt_lineage or []:
        await conn.execute(
            """
            INSERT INTO prompt_lineage (prompt_hash, session_id, correlation_id, data, created_at)
            VALUES ($1,$2,$3,$4::jsonb,$5)
            ON CONFLICT (prompt_hash, session_id) DO UPDATE SET data = EXCLUDED.data
            """,
            pl.prompt_hash,
            pl.session_id,
            pl.correlation_id,
            pl.model_dump_json(),
            pl.created_at,
        )
    for anom in payload.runtime_anomalies or []:
        await conn.execute(
            """
            INSERT INTO runtime_anomalies (session_id, correlation_id, data, severity, detected_at)
            VALUES ($1,$2,$3::jsonb,$4,$5)
            """,
            anom.session_id,
            anom.correlation_id,
            anom.model_dump_json(),
            anom.severity.value,
            anom.detected_at,
        )
    if payload.session_diagnostics:
        d = payload.session_diagnostics
        await conn.execute(
            """
            INSERT INTO session_diagnostics (session_id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data, correlation_id = EXCLUDED.correlation_id
            """,
            d.session_id,
            d.correlation_id,
            d.model_dump_json(),
            now,
        )
