"""Outbox processor — process after success, SKIP LOCKED, FIFO by correlation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.health import agent_health_registry
from core.persistence import get_pool
from schemas.runtime import OutboxEvent


async def _handle_event(event: OutboxEvent) -> bool:
    try:
        if event.event_type == "decision.recorded":
            agent = event.payload.get("agent", "unknown")
            if isinstance(agent, str):
                agent_health_registry.record_run_sync(agent, success=True, latency_ms=0)
        return True
    except Exception:
        return False


async def process_outbox_batch(conn, limit: int = 50) -> int:
    rows = await conn.fetch(
        """
        SELECT * FROM outbox_events
        WHERE processed = FALSE
        ORDER BY correlation_id ASC, created_at ASC
        LIMIT $1
        FOR UPDATE SKIP LOCKED
        """,
        limit,
    )
    from core.persistence import _row_to_outbox

    processed = 0
    for row in rows:
        event = _row_to_outbox(row)
        if not await _handle_event(event):
            continue
        result = await conn.execute(
            """
            UPDATE outbox_events SET processed = TRUE
            WHERE idempotency_key = $1 AND processed = FALSE
            """,
            event.idempotency_key,
        )
        if result.endswith("1"):
            await conn.execute(
                """
                INSERT INTO processed_idempotency (idempotency_key, processed_at)
                VALUES ($1, $2)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                event.idempotency_key,
                datetime.now(timezone.utc),
            )
            processed += 1
    return processed


async def process_outbox_batch_memory(limit: int = 50) -> int:
    from core.persistence import _in_memory_outbox, _processed_idempotency

    events = sorted(
        [e for e in _in_memory_outbox if not e.processed],
        key=lambda e: (e.correlation_id, e.created_at),
    )[:limit]
    processed = 0
    for event in events:
        if event.idempotency_key in _processed_idempotency:
            continue
        if not await _handle_event(event):
            continue
        event.processed = True
        _processed_idempotency.add(event.idempotency_key)
        processed += 1
    return processed


async def process_outbox_batch_auto(limit: int = 50) -> int:
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                return await process_outbox_batch(conn, limit)
    return await process_outbox_batch_memory(limit)


async def run_outbox_worker(interval_seconds: float = 5.0) -> None:
    while True:
        await process_outbox_batch_auto()
        await asyncio.sleep(interval_seconds)
