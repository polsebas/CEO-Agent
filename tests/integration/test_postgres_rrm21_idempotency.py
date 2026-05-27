"""Postgres — RRM-2.1 idempotent outbox retains spans."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import get_pool, get_replay_baseline_meta, query_execution_spans, query_runtime_health
from core.spans import span_manager
from core.transaction import PersistRuntimePayload, persist_runtime_tx
from schemas.spans import SpanStatus, SpanType
from tests.gate.test_idempotent_outbox_contract import _run_idempotent_founder_intent_retry


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_outbox_persists_late_spans(postgres_available):
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


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_session_completed_materializes_baseline(postgres_available):
    pool = await get_pool()
    session_id = f"pg-idem-close-{uuid4()}"
    correlation_id = f"pg-idem-close-corr-{uuid4()}"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )

    baseline_before = await get_replay_baseline_meta(session_id)
    assert baseline_before is not None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT payload FROM outbox_events
            WHERE correlation_id = $1 AND event_type = 'session.completed'
            """,
            correlation_id,
        )
        assert row is not None
        raw_payload = row["payload"]
        event_payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload

        r2 = await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="session.completed",
                event_payload=event_payload,
                business_key="session.completed",
                store_replay_baseline=True,
            ),
        )
        assert r2.inserted is False

        baseline_after = await get_replay_baseline_meta(session_id, conn=conn)
        health_rows = await query_runtime_health(session_id, conn=conn)

    assert baseline_after is not None
    assert baseline_after["outcome_fingerprint"] == baseline_before["outcome_fingerprint"]
    assert health_rows
    assert health_rows[-1].replay_confidence == 1.0


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_retry_same_trace_no_loss_no_dup(postgres_available):
    pool = await get_pool()
    sid, cid = f"contract-idem-pg-{uuid4()}", f"contract-idem-pg-corr-{uuid4()}"
    async with pool.acquire() as conn:
        await _run_idempotent_founder_intent_retry(conn, sid=sid, cid=cid)


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_replay_same_span_id_no_duplicate(postgres_available):
    pool = await get_pool()
    sid, cid = f"contract-span-dedup-{uuid4()}", f"contract-span-dedup-corr-{uuid4()}"
    base = dict(
        correlation_id=cid,
        session_id=sid,
        event_type="founder.intent",
        event_payload={"message": "dedup"},
        business_key="founder.intent",
    )

    async with pool.acquire() as conn:
        span_manager.begin_session(session_id=sid, correlation_id=cid)
        orch = span_manager.start(SpanType.ORCHESTRATION)
        span_manager.end(orch, status=SpanStatus.OK)
        await persist_runtime_tx(conn, PersistRuntimePayload(**base))

        updated = orch.model_copy(update={"metadata": {"retried": True}})
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(**base, execution_spans=[updated], drain_spans=False),
        )
        spans = await query_execution_spans(sid, correlation_id=cid, conn=conn)

    assert len(spans) == 1
    assert spans[0].metadata.get("retried") is True


@pytest.mark.postgres
@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_postgres_idempotent_session_completed_baseline_and_health(postgres_available):
    pool = await get_pool()
    session_id = f"contract-close-{uuid4()}"
    correlation_id = f"contract-close-corr-{uuid4()}"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT payload FROM outbox_events
            WHERE correlation_id = $1 AND event_type = 'session.completed'
            """,
            correlation_id,
        )
        assert row is not None
        raw_payload = row["payload"]
        event_payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload

        r2 = await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="session.completed",
                event_payload=event_payload,
                business_key="session.completed",
                store_replay_baseline=True,
            ),
        )
        assert r2.inserted is False

        close_events = await conn.fetch(
            """
            SELECT idempotency_key FROM outbox_events
            WHERE correlation_id = $1 AND event_type = 'session.completed'
            """,
            correlation_id,
        )
        health_rows = await query_runtime_health(session_id, conn=conn)

    assert len(close_events) == 1
    baseline = await get_replay_baseline_meta(session_id)
    assert baseline is not None
    assert health_rows
    assert health_rows[-1].replay_confidence == 1.0
    assert len({h.correlation_id for h in health_rows if h.correlation_id == correlation_id}) == 1
