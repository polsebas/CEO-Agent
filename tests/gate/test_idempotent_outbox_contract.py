"""Contract: idempotent outbox retry — same trace_id, no span loss, no duplication."""

from __future__ import annotations

import pytest

from core.intelligence_persist import apply_intelligence_memory
from core.persistence import (
    get_events_by_correlation,
    query_execution_spans,
    reset_in_memory_store,
)
from core.runtime_session import MemoryConnection
from core.spans import span_manager
from core.telemetry.otel import trace_id_from_correlation
from core.transaction import PersistRuntimePayload, _idempotency_key, persist_runtime_tx
from schemas.spans import ExecutionSpan, SpanStatus, SpanType


async def _run_idempotent_founder_intent_retry(
    conn,
    *,
    sid: str,
    cid: str,
    message: str = "contract-idem",
) -> tuple[object, object, list[ExecutionSpan]]:
    base = dict(
        correlation_id=cid,
        session_id=sid,
        event_type="founder.intent",
        event_payload={"message": message},
        business_key="founder.intent",
    )
    idem = _idempotency_key(cid, "founder.intent", {"message": message}, "founder.intent")

    span_manager.begin_session(session_id=sid, correlation_id=cid)
    orch = span_manager.start(SpanType.ORCHESTRATION)
    span_manager.end(orch, status=SpanStatus.OK)
    r1 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
    assert r1.inserted is True

    span_manager.begin_session(session_id=sid, correlation_id=cid)
    transition = span_manager.start(SpanType.TRANSITION)
    span_manager.end(transition, status=SpanStatus.OK)
    r2 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
    assert r2.inserted is False

    events = await get_events_by_correlation(cid, conn=conn)
    matching = [e for e in events if e.idempotency_key == idem]
    assert len(matching) == 1

    spans = await query_execution_spans(sid, correlation_id=cid, conn=conn)
    expected_trace = trace_id_from_correlation(cid)
    assert all(s.trace_id == expected_trace for s in spans)
    types = {s.span_type for s in spans}
    assert SpanType.ORCHESTRATION in types
    assert SpanType.TRANSITION in types
    span_ids = [s.span_id for s in spans]
    assert len(span_ids) == len(set(span_ids))

    return r1, r2, spans


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_idempotent_retry_same_trace_no_loss_no_dup_memory():
    reset_in_memory_store()
    conn = MemoryConnection()
    sid, cid = "contract-idem-mem", "contract-idem-mem-corr"
    await _run_idempotent_founder_intent_retry(conn, sid=sid, cid=cid)


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_memory_append_spans_dedup_by_span_id():
    reset_in_memory_store()
    sid, cid = "contract-dedup", "contract-dedup-corr"
    span = ExecutionSpan(
        span_id="span-dedup-1",
        trace_id=trace_id_from_correlation(cid),
        correlation_id=cid,
        session_id=sid,
        span_type=SpanType.ORCHESTRATION,
        status=SpanStatus.OK,
    )
    updated = span.model_copy(update={"metadata": {"version": 2}})
    apply_intelligence_memory(
        PersistRuntimePayload(
            correlation_id=cid,
            session_id=sid,
            event_type="probe",
            event_payload={},
            execution_spans=[span],
            drain_spans=False,
        )
    )
    apply_intelligence_memory(
        PersistRuntimePayload(
            correlation_id=cid,
            session_id=sid,
            event_type="probe",
            event_payload={},
            execution_spans=[updated],
            drain_spans=False,
        )
    )
    rows = await query_execution_spans(sid, correlation_id=cid)
    assert len(rows) == 1
    assert rows[0].metadata.get("version") == 2
