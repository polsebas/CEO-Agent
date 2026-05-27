"""Postgres — RRM-2.1 idempotent outbox retains spans."""

from __future__ import annotations

import pytest

from core.persistence import get_pool, init_schema, query_execution_spans
from core.spans import span_manager
from core.transaction import PersistRuntimePayload, persist_runtime_tx
from schemas.spans import SpanStatus, SpanType


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_outbox_persists_late_spans(postgres_available):
    await init_schema()
    pool = await get_pool()
    sid, cid = "pg-rrm21-idem", "pg-rrm21-idem-corr"
    base = dict(
        correlation_id=cid,
        session_id=sid,
        event_type="founder.intent",
        event_payload={"message": "idem"},
        business_key="founder.intent",
    )

    async with pool.acquire() as conn:
        span_manager.begin_session(session_id=sid, correlation_id=cid)
        o = span_manager.start(SpanType.ORCHESTRATION)
        span_manager.end(o, status=SpanStatus.OK)
        r1 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
        assert r1.inserted is True

        span_manager.begin_session(session_id=sid, correlation_id=cid)
        t = span_manager.start(SpanType.TRANSITION)
        span_manager.end(t, status=SpanStatus.OK)
        r2 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
        assert r2.inserted is False

        spans = await query_execution_spans(sid, correlation_id=cid, conn=conn)

    types = {s.span_type for s in spans}
    assert SpanType.ORCHESTRATION in types
    assert SpanType.TRANSITION in types
