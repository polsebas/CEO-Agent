"""Persistence layer: Postgres outbox + world state with in-memory fallback."""

from __future__ import annotations

import json
from datetime import datetime
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
    *,
    correlation_id: str,
    event_type: str,
    event_payload: dict,
    decision: DecisionRecord | None = None,
    side_effect: SideEffectRecord | None = None,
    causation_id: str | None = None,
) -> OutboxEvent:
    """Atomic decision + side effect + outbox append in a single transaction."""
    event = OutboxEvent(
        id=str(uuid4()),
        idempotency_key=f"{correlation_id}:{event_type}:{uuid4()}",
        correlation_id=correlation_id,
        causation_id=causation_id,
        event_type=event_type,
        payload=event_payload,
        world_state_version=get_world_state().version,
        created_at=datetime.utcnow(),
    )
    if decision:
        _in_memory_decisions.append(decision)
    if side_effect:
        _in_memory_effects.append(side_effect)
    _in_memory_outbox.append(event)

    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if decision:
                    await conn.execute(
                        "INSERT INTO decision_records (id, correlation_id, data, created_at) VALUES ($1,$2,$3::jsonb,$4)",
                        decision.id,
                        decision.correlation_id,
                        decision.model_dump_json(),
                        decision.created_at,
                    )
                if side_effect:
                    await conn.execute(
                        "INSERT INTO side_effect_records (id, correlation_id, data, created_at) VALUES ($1,$2,$3::jsonb,$4)",
                        side_effect.id,
                        side_effect.correlation_id,
                        side_effect.model_dump_json(),
                        side_effect.created_at,
                    )
                await conn.execute(
                    """
                    INSERT INTO outbox_events
                    (id, idempotency_key, correlation_id, causation_id, event_type, payload, world_state_version, processed, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,FALSE,$8)
                    """,
                    event.id,
                    event.idempotency_key,
                    event.correlation_id,
                    event.causation_id,
                    event.event_type,
                    json.dumps(event.payload),
                    event.world_state_version,
                    event.created_at,
                )
    return event


async def append_outbox_event(
    *,
    correlation_id: str,
    causation_id: str | None,
    event_type: str,
    payload: dict,
    world_state_version: int | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        id=str(uuid4()),
        idempotency_key=f"{correlation_id}:{event_type}:{uuid4()}",
        correlation_id=correlation_id,
        causation_id=causation_id,
        event_type=event_type,
        payload=payload,
        world_state_version=world_state_version or get_world_state().version,
        created_at=datetime.utcnow(),
    )
    _in_memory_outbox.append(event)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO outbox_events
                    (id, idempotency_key, correlation_id, causation_id, event_type, payload, world_state_version, processed, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,FALSE,$8)
                    """,
                    event.id,
                    event.idempotency_key,
                    event.correlation_id,
                    event.causation_id,
                    event.event_type,
                    json.dumps(event.payload),
                    event.world_state_version,
                    event.created_at,
                )
    return event


async def save_decision(record: DecisionRecord) -> None:
    _in_memory_decisions.append(record)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO decision_records (id, correlation_id, data, created_at) VALUES ($1,$2,$3::jsonb,$4)",
                record.id,
                record.correlation_id,
                record.model_dump_json(),
                record.created_at,
            )


async def save_side_effect(record: SideEffectRecord) -> None:
    _in_memory_effects.append(record)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO side_effect_records (id, correlation_id, data, created_at) VALUES ($1,$2,$3::jsonb,$4)",
                record.id,
                record.correlation_id,
                record.model_dump_json(),
                record.created_at,
            )


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


async def get_events_by_correlation(correlation_id: str) -> list[OutboxEvent]:
    memory = sorted(
        [e for e in _in_memory_outbox if e.correlation_id == correlation_id],
        key=lambda e: e.created_at,
    )
    if memory:
        return memory
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM outbox_events WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [_row_to_outbox(r) for r in rows]
    return sorted(
        [e for e in _in_memory_outbox if e.correlation_id == correlation_id],
        key=lambda e: e.created_at,
    )


async def get_decisions_by_correlation(correlation_id: str) -> list[DecisionRecord]:
    memory = [d for d in _in_memory_decisions if d.correlation_id == correlation_id]
    if memory:
        return memory
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM decision_records WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [DecisionRecord.model_validate_json(r["data"]) for r in rows]
    return [d for d in _in_memory_decisions if d.correlation_id == correlation_id]


async def get_effects_by_correlation(correlation_id: str) -> list[SideEffectRecord]:
    memory = [e for e in _in_memory_effects if e.correlation_id == correlation_id]
    if memory:
        return memory
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM side_effect_records WHERE correlation_id = $1 ORDER BY created_at ASC",
                correlation_id,
            )
            return [SideEffectRecord.model_validate_json(r["data"]) for r in rows]
    return [e for e in _in_memory_effects if e.correlation_id == correlation_id]


async def save_replay_snapshot(session_id: str, correlation_id: str, step: int, data: dict) -> None:
    from core.replay_store import save_replay_snapshot_memory

    save_replay_snapshot_memory(session_id, step, data)
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO replay_snapshots (session_id, correlation_id, step, data)
                VALUES ($1,$2,$3,$4::jsonb)
                ON CONFLICT (session_id, step) DO UPDATE SET data = EXCLUDED.data
                """,
                session_id,
                correlation_id,
                step,
                json.dumps(data),
            )


async def get_replay_snapshots(session_id: str) -> list[dict]:
    from core.replay_store import get_replay_snapshots_memory

    memory = get_replay_snapshots_memory(session_id)
    if memory:
        return memory
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
                datetime.utcnow(),
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


def reset_in_memory_store() -> None:
    global _world_state, _pool
    _in_memory_outbox.clear()
    _in_memory_decisions.clear()
    _in_memory_effects.clear()
    _in_memory_snapshots.clear()
    _in_memory_agent_health.clear()
    _processed_idempotency.clear()
    _world_state = default_world_state()
    _pool = None
