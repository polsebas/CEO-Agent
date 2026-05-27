"""RRM-2A — execution spans gate."""

from __future__ import annotations

import time

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import query_execution_spans, reset_in_memory_store
from schemas.spans import SpanType


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_founder_session_span_chain():
    reset_in_memory_store()
    session_id = "rrm2-spans"
    correlation_id = "rrm2-spans-corr"
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert "error" not in result
    spans = await query_execution_spans(session_id, correlation_id=correlation_id)
    assert len(spans) >= 3
    types = {s.span_type for s in spans}
    assert SpanType.ORCHESTRATION in types
    assert SpanType.TRANSITION in types
    assert SpanType.TOOL_EXECUTION in types or SpanType.AGENT_REASONING in types
    for s in spans:
        assert s.session_id == session_id
        assert s.correlation_id == correlation_id
        assert s.trace_id


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_no_orphan_spans_except_roots():
    reset_in_memory_store()
    session_id = "rrm2-orphan"
    correlation_id = "rrm2-orphan-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    spans = await query_execution_spans(session_id, correlation_id=correlation_id)
    ids = {s.span_id for s in spans}
    for s in spans:
        if s.parent_span_id:
            assert s.parent_span_id in ids


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_span_persist_overhead_under_budget():
    reset_in_memory_store()
    session_id = "rrm2-perf"
    correlation_id = "rrm2-perf-corr"
    t0 = time.perf_counter()
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    spans = await query_execution_spans(session_id, correlation_id=correlation_id)
    assert len(spans) >= 1
    amortized = elapsed_ms / len(spans)
    assert amortized < 500
