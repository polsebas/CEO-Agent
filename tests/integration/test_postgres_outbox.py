"""Postgres outbox concurrency — RRM1.5-M5 (SKIP LOCKED)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.persistence import get_pool
from workers.outbox_processor import process_outbox_batch


@pytest.mark.postgres
@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_postgres_outbox_two_workers_no_double_process(postgres_available):
    pool = await get_pool()
    assert pool is not None

    idem = f"pg-outbox-{uuid4()}"
    corr = f"pg-outbox-corr-{uuid4()}"
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO outbox_events
            (id, idempotency_key, correlation_id, causation_id, event_type, payload,
             world_state_version, processed, created_at)
            VALUES ($1,$2,$3,NULL,'test.outbox',$4::jsonb,0,FALSE,$5)
            """,
            str(uuid4()),
            idem,
            corr,
            '{"probe": true}',
            now,
        )

    async def worker() -> int:
        async with pool.acquire() as conn:
            async with conn.transaction():
                return await process_outbox_batch(conn, limit=10)

    first, second = await asyncio.gather(worker(), worker())
    assert first + second == 1

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT processed FROM outbox_events WHERE idempotency_key = $1",
            idem,
        )
    assert row is not None
    assert row["processed"] is True
