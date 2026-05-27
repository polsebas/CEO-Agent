"""Persistence layer: Postgres outbox + world state with in-memory fallback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from schemas.decisions import DecisionRecord
from schemas.effects import SideEffectRecord
from schemas.runtime import OutboxEvent
from schemas.world import WorldState, WorldStateSnapshot, default_world_state

_in_memory_outbox: list[OutboxEvent] = []
_in_memory_decisions: list[DecisionRecord] = []
_in_memory_effects: list[SideEffectRecord] = []
_in_memory_snapshots: list[WorldStateSnapshot] = []
_in_memory_agent_health: dict[str, dict] = {}
_in_memory_runtime_transitions: list[dict] = []
_processed_idempotency: set[str] = set()
_world_state: WorldState = default_world_state()
_pool = None


async def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    from core.config import settings

    if settings.use_in_memory_store:
        return None
    try:
        import asyncpg

        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
        )
        await init_schema(_pool)
        return _pool
    except Exception:
        return None


async def init_schema(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox_events (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                correlation_id TEXT NOT NULL,
                causation_id TEXT,
                event_type TEXT NOT NULL,
                payload JSONB NOT NULL,
                world_state_version INT NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_correlation ON outbox_events(correlation_id);
            CREATE INDEX IF NOT EXISTS idx_outbox_unprocessed ON outbox_events(processed) WHERE processed = FALSE;

            CREATE TABLE IF NOT EXISTS world_state_snapshots (
                version INT PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                changed_entities JSONB,
                checksum TEXT NOT NULL,
                state JSONB NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decision_records (
                id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS side_effect_records (
                id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS replay_snapshots (
                session_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                step INT NOT NULL,
                data JSONB NOT NULL,
                PRIMARY KEY (session_id, step)
            );

            CREATE TABLE IF NOT EXISTS agent_health (
                agent_id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS structured_retry_traces (
                id SERIAL PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                step_id INT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                UNIQUE (correlation_id, session_id, agent_id, step_id)
            );

            CREATE TABLE IF NOT EXISTS runtime_transitions (
                id SERIAL PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS governance_audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                action_hash TEXT NOT NULL,
                data JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL,
                UNIQUE (action_hash)
            );

            CREATE TABLE IF NOT EXISTS replay_baselines (
                session_id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                outcome_fingerprint TEXT NOT NULL,
                orchestrator_version TEXT,
                created_at TIMESTAMPTZ NOT NULL
            );
            ALTER TABLE replay_baselines ADD COLUMN IF NOT EXISTS orchestrator_version TEXT;

            CREATE TABLE IF NOT EXISTS processed_idempotency (
                idempotency_key TEXT PRIMARY KEY,
                processed_at TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS execution_spans (
                span_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                parent_span_id TEXT,
                span_type TEXT NOT NULL,
                runtime_state TEXT,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_spans_session_corr ON execution_spans(session_id, correlation_id);
            CREATE INDEX IF NOT EXISTS idx_spans_parent ON execution_spans(parent_span_id);
            CREATE INDEX IF NOT EXISTS idx_spans_trace ON execution_spans(trace_id);

            CREATE TABLE IF NOT EXISTS cognitive_telemetry (
                id SERIAL PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cog_session ON cognitive_telemetry(session_id, correlation_id, created_at);

            CREATE TABLE IF NOT EXISTS runtime_health_snapshots (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_health_session ON runtime_health_snapshots(session_id, generated_at DESC);

            CREATE TABLE IF NOT EXISTS prompt_lineage (
                prompt_hash TEXT NOT NULL,
                session_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (prompt_hash, session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_lineage_session ON prompt_lineage(session_id);

            CREATE TABLE IF NOT EXISTS runtime_anomalies (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                severity TEXT NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_anom_session ON runtime_anomalies(session_id, severity, detected_at);

            CREATE TABLE IF NOT EXISTS session_diagnostics (
                session_id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );
            """
        )


def get_world_state() -> WorldState:
    return _world_state


def update_world_state(state: WorldState, changed_entities: list[str] | None = None) -> WorldStateSnapshot:
    global _world_state
    state.version = _world_state.version + 1
    _world_state = state
    snapshot = WorldStateSnapshot.from_state(state, changed_entities)
    _in_memory_snapshots.append(snapshot)
    return snapshot


async def persist_execution_bundle(
    conn,
    *,
    correlation_id: str,
    event_type: str,
    event_payload: dict,
    decision: DecisionRecord | None = None,
    side_effect: SideEffectRecord | None = None,
    causation_id: str | None = None,
    session_id: str | None = None,
) -> OutboxEvent:
    from core.transaction import PersistRuntimePayload, persist_runtime_tx

    sid = session_id or correlation_id
    result = await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=correlation_id,
            session_id=sid,
            event_type=event_type,
            event_payload=event_payload,
            causation_id=causation_id,
            decision=decision,
            side_effect=side_effect,
            business_key=event_type,
        ),
    )
    return result.event


async def append_outbox_event(
    conn,
    *,
    correlation_id: str,
    causation_id: str | None,
    event_type: str,
    payload: dict,
    session_id: str | None = None,
) -> OutboxEvent:
    from core.transaction import PersistRuntimePayload, persist_runtime_tx

    result = await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=correlation_id,
            session_id=session_id or correlation_id,
            event_type=event_type,
            event_payload=payload,
            causation_id=causation_id,
            business_key=event_type,
        ),
    )
    return result.event


async def save_decision(record: DecisionRecord) -> None:
    """Deprecated — use persist_runtime_tx(conn, ...) inside mutative_session."""
    from core.config import settings

    if not settings.use_in_memory_store:
        raise RuntimeError("save_decision is in-memory only; use persist_runtime_tx with conn")
    _in_memory_decisions.append(record)


async def save_side_effect(record: SideEffectRecord) -> None:
    """Deprecated — use persist_runtime_tx(conn, ...) inside mutative_session."""
    from core.config import settings

    if not settings.use_in_memory_store:
        raise RuntimeError("save_side_effect is in-memory only; use persist_runtime_tx with conn")
    _in_memory_effects.append(record)


async def fetch_unprocessed_events(limit: int = 100) -> list[OutboxEvent]:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM outbox_events WHERE processed = FALSE ORDER BY created_at ASC LIMIT $1",
                limit,
            )
            return [_row_to_outbox(r) for r in rows]
    return [e for e in _in_memory_outbox if not e.processed][:limit]


async def mark_event_processed(idempotency_key: str) -> bool:
    if idempotency_key in _processed_idempotency:
        return False
    _processed_idempotency.add(idempotency_key)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE outbox_events SET processed = TRUE WHERE idempotency_key = $1 AND processed = FALSE",
                idempotency_key,
            )
            return result.endswith("1")
    for event in _in_memory_outbox:
        if event.idempotency_key == idempotency_key:
            event.processed = True
            return True
    return False


async def get_events_by_correlation(correlation_id: str, *, conn=None) -> list[OutboxEvent]:
    from core.config import settings
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return sorted(
            [e for e in _in_memory_outbox if e.correlation_id == correlation_id],
            key=lambda e: e.created_at,
        )
    if conn is not None:
        rows = await conn.fetch(
            "SELECT * FROM outbox_events WHERE correlation_id = $1 ORDER BY created_at ASC",
            correlation_id,
        )
        return [_row_to_outbox(r) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM outbox_events WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [_row_to_outbox(r) for r in rows]
    return []


async def get_decisions_by_correlation(correlation_id: str, *, conn=None) -> list[DecisionRecord]:
    from core.config import settings
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return [d for d in _in_memory_decisions if d.correlation_id == correlation_id]
    if conn is not None:
        rows = await conn.fetch(
            "SELECT data FROM decision_records WHERE correlation_id = $1 ORDER BY created_at ASC",
            correlation_id,
        )
        return [DecisionRecord.model_validate_json(r["data"]) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM decision_records WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [DecisionRecord.model_validate_json(r["data"]) for r in rows]
    return []


async def get_effects_by_correlation(correlation_id: str, *, conn=None) -> list[SideEffectRecord]:
    from core.config import settings
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return [e for e in _in_memory_effects if e.correlation_id == correlation_id]
    if conn is not None:
        rows = await conn.fetch(
            "SELECT data FROM side_effect_records WHERE correlation_id = $1 ORDER BY created_at ASC",
            correlation_id,
        )
        return [SideEffectRecord.model_validate_json(r["data"]) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM side_effect_records WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [SideEffectRecord.model_validate_json(r["data"]) for r in rows]
    return []


async def save_replay_snapshot(
    conn,
    session_id: str,
    correlation_id: str,
    step: int,
    data: dict,
) -> None:
    """Deprecated: use persist_runtime_tx(conn, ...) with replay_snapshot."""
    from core.transaction import PersistRuntimePayload, persist_runtime_tx

    await persist_runtime_tx(
        conn,
        PersistRuntimePayload(
            correlation_id=correlation_id,
            session_id=session_id,
            event_type="replay.snapshot",
            event_payload={"step": step},
            replay_snapshot=data,
            replay_step=step,
            business_key=f"replay:{step}",
        ),
    )


async def get_replay_snapshots(session_id: str, *, conn=None) -> list[dict]:
    from core.config import settings
    from core.replay_store import get_replay_snapshots_memory
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_replay_snapshots_memory(session_id)
    if conn is not None:
        rows = await conn.fetch(
            "SELECT data FROM replay_snapshots WHERE session_id = $1 ORDER BY step ASC",
            session_id,
        )
        return [json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM replay_snapshots WHERE session_id = $1 ORDER BY step ASC",
                session_id,
            )
            return [json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows]
    return []


async def health_check_db() -> bool:
    from core.config import settings

    if settings.use_in_memory_store:
        return True
    pool = await get_pool()
    if not pool:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def save_agent_health(agent_id: str, data: dict) -> None:
    _in_memory_agent_health[agent_id] = data
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_health (agent_id, data, updated_at)
                VALUES ($1, $2::jsonb, $3)
                ON CONFLICT (agent_id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
                """,
                agent_id,
                json.dumps(data),
                datetime.now(timezone.utc),
            )


async def load_agent_health(agent_id: str) -> dict | None:
    if agent_id in _in_memory_agent_health:
        return _in_memory_agent_health[agent_id]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT data FROM agent_health WHERE agent_id = $1", agent_id)
            if row:
                data = row["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                _in_memory_agent_health[agent_id] = data
                return data
    return None


async def load_all_agent_health() -> dict[str, dict]:
    result = dict(_in_memory_agent_health)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT agent_id, data FROM agent_health")
            for row in rows:
                data = row["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                result[row["agent_id"]] = data
    return result



def _row_to_outbox(row) -> OutboxEvent:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return OutboxEvent(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        event_type=row["event_type"],
        payload=payload,
        world_state_version=row["world_state_version"],
        processed=row["processed"],
        created_at=row["created_at"],
    )


def apply_memory_runtime_persist(payload, event: OutboxEvent, world_snap: WorldStateSnapshot | None) -> None:
    """In-memory path for tests and use_in_memory_store mode."""
    global _world_state
    from core.intelligence_persist import apply_intelligence_memory

    if payload.decision:
        _in_memory_decisions.append(payload.decision)
    if payload.side_effect:
        _in_memory_effects.append(payload.side_effect)
    _in_memory_outbox.append(event)
    if world_snap:
        _in_memory_snapshots.append(world_snap)
        _world_state = WorldState.model_validate(world_snap.state)
    if payload.runtime_transition:
        rt = payload.runtime_transition
        _in_memory_runtime_transitions.append(
            {
                "correlation_id": rt.correlation_id,
                "session_id": rt.session_id,
                "from_state": rt.from_state,
                "to_state": rt.to_state,
            }
        )
    if payload.replay_snapshot is not None and payload.replay_step is not None:
        from core.replay_store import save_replay_snapshot_memory

        save_replay_snapshot_memory(payload.session_id, payload.replay_step, payload.replay_snapshot)
    if payload.retry_trace:
        from core.intelligence_store import append_retry_trace

        append_retry_trace(payload.retry_trace.model_dump(mode="json"))
    apply_intelligence_memory(payload)


async def get_runtime_transitions(session_id: str, *, conn=None) -> list:
    from core.config import settings
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return [t for t in _in_memory_runtime_transitions if t["session_id"] == session_id]
    if conn is not None:
        rows = await conn.fetch(
            """
            SELECT correlation_id, session_id, from_state, to_state
            FROM runtime_transitions
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id,
        )
        return [dict(r) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await get_runtime_transitions(session_id, conn=c)
    return []


async def get_replay_baseline_meta(session_id: str, *, conn=None) -> dict | None:
    from core.config import settings
    from core.replay_store import get_baseline_record_memory
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_baseline_record_memory(session_id)
    if conn is not None:
        row = await conn.fetchrow(
            """
            SELECT correlation_id, outcome_fingerprint, orchestrator_version
            FROM replay_baselines WHERE session_id = $1
            """,
            session_id,
        )
        if not row:
            return None
        return {
            "correlation_id": row["correlation_id"],
            "outcome_fingerprint": row["outcome_fingerprint"],
            "orchestrator_version": row["orchestrator_version"] or "rrm15-legacy",
        }
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await get_replay_baseline_meta(session_id, conn=c)
    return None


async def get_replay_baseline(session_id: str, *, conn=None) -> str | None:
    from core.config import settings
    from core.replay_store import get_baseline_fingerprint_memory
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_baseline_fingerprint_memory(session_id)
    if conn is not None:
        row = await conn.fetchrow(
            "SELECT outcome_fingerprint FROM replay_baselines WHERE session_id = $1",
            session_id,
        )
        return row["outcome_fingerprint"] if row else None
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await get_replay_baseline(session_id, conn=c)
    return None


async def query_execution_spans(
    session_id: str,
    *,
    correlation_id: str | None = None,
    conn=None,
) -> list:
    from core.config import settings
    from core.intelligence_store import get_spans
    from core.runtime_session import MemoryConnection
    from schemas.spans import ExecutionSpan

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_spans(session_id, correlation_id=correlation_id)
    if conn is not None:
        q = "SELECT * FROM execution_spans WHERE session_id = $1"
        args: list = [session_id]
        if correlation_id:
            q += " AND correlation_id = $2"
            args.append(correlation_id)
        q += " ORDER BY started_at ASC"
        rows = await conn.fetch(q, *args)
        return [_row_to_span(r) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await query_execution_spans(session_id, correlation_id=correlation_id, conn=c)
    return []


async def query_cognitive_telemetry(session_id: str, *, correlation_id: str | None = None, conn=None) -> list:
    from core.config import settings
    from core.intelligence_store import get_telemetry
    from core.runtime_session import MemoryConnection
    from schemas.cognition import CognitiveTelemetry

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_telemetry(session_id, correlation_id=correlation_id)
    if conn is not None:
        q = "SELECT data FROM cognitive_telemetry WHERE session_id = $1"
        args: list = [session_id]
        if correlation_id:
            q += " AND correlation_id = $2"
            args.append(correlation_id)
        q += " ORDER BY created_at ASC"
        rows = await conn.fetch(q, *args)
        return [CognitiveTelemetry.model_validate(_json_data(r["data"])) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await query_cognitive_telemetry(session_id, correlation_id=correlation_id, conn=c)
    return []


async def query_runtime_health(session_id: str, *, conn=None) -> list:
    from core.config import settings
    from core.intelligence_store import get_health_snapshots
    from core.runtime_session import MemoryConnection
    from schemas.runtime_health import RuntimeHealth

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_health_snapshots(session_id)
    if conn is not None:
        rows = await conn.fetch(
            "SELECT data FROM runtime_health_snapshots WHERE session_id = $1 ORDER BY generated_at DESC",
            session_id,
        )
        return [RuntimeHealth.model_validate(_json_data(r["data"])) for r in rows]
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await query_runtime_health(session_id, conn=c)
    return []


async def query_session_diagnostics_row(session_id: str, *, conn=None):
    from core.config import settings
    from core.intelligence_store import get_session_diagnostics
    from core.runtime_session import MemoryConnection
    from schemas.diagnostics import SessionDiagnostics

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return get_session_diagnostics(session_id)
    if conn is not None:
        row = await conn.fetchrow(
            "SELECT data FROM session_diagnostics WHERE session_id = $1",
            session_id,
        )
        if not row:
            return None
        return SessionDiagnostics.model_validate(_json_data(row["data"]))
    pool = await get_pool()
    if pool:
        async with pool.acquire() as c:
            return await query_session_diagnostics_row(session_id, conn=c)
    return None


def _json_data(val):
    if isinstance(val, str):
        return json.loads(val)
    return val


def _row_to_span(row) -> "ExecutionSpan":
    from schemas.spans import ExecutionSpan, SpanStatus, SpanType

    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return ExecutionSpan(
        span_id=row["span_id"],
        trace_id=row["trace_id"],
        correlation_id=row["correlation_id"],
        session_id=row["session_id"],
        parent_span_id=row["parent_span_id"],
        span_type=SpanType(row["span_type"]),
        runtime_state=row["runtime_state"] or "",
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        status=SpanStatus(row["status"]),
        metadata=meta or {},
    )


def get_memory_outbox_by_idempotency(idempotency_key: str) -> OutboxEvent | None:
    for event in reversed(_in_memory_outbox):
        if event.idempotency_key == idempotency_key:
            return event
    return None


def reset_in_memory_store() -> None:
    global _world_state, _pool
    from core.governance_store import reset_governance_memory
    from core.intelligence_store import reset_intelligence_store
    from core.prompt_lineage import prompt_lineage_tracker

    reset_intelligence_store()
    prompt_lineage_tracker._last_hash.clear()
    _in_memory_outbox.clear()
    _in_memory_decisions.clear()
    _in_memory_effects.clear()
    _in_memory_snapshots.clear()
    _in_memory_runtime_transitions.clear()
    _in_memory_agent_health.clear()
    _processed_idempotency.clear()
    from core.replay_store import reset_replay_store

    reset_replay_store()
    _world_state = default_world_state()
    _pool = None
    reset_governance_memory()
