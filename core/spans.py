"""Execution span manager — OTel dual-write + TX payload accumulation."""

from __future__ import annotations

import contextvars
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.telemetry.otel import end_otel_span, start_otel_span, trace_id_from_correlation
from schemas.spans import ExecutionSpan, SpanStatus, SpanType

_pending_spans: contextvars.ContextVar[list[ExecutionSpan] | None] = contextvars.ContextVar(
    "pending_spans", default=None
)
_active_parents: contextvars.ContextVar[dict[SpanType, str] | None] = contextvars.ContextVar(
    "active_parents", default=None
)
_session_ctx: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "span_session_ctx", default=None
)
_otel_by_span_id: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "otel_by_span_id", default=None
)


def _pending_list() -> list[ExecutionSpan]:
    val = _pending_spans.get()
    if val is None:
        val = []
        _pending_spans.set(val)
    return val


def _parents_map() -> dict[SpanType, str]:
    val = _active_parents.get()
    if val is None:
        val = {}
        _active_parents.set(val)
    return val


def _session_context() -> dict[str, str]:
    val = _session_ctx.get()
    if val is None:
        val = {}
        _session_ctx.set(val)
    return val


def _otel_map() -> dict[str, Any]:
    val = _otel_by_span_id.get()
    if val is None:
        val = {}
        _otel_by_span_id.set(val)
    return val


def begin_session(*, session_id: str, correlation_id: str) -> None:
    _pending_spans.set([])
    _active_parents.set({})
    _session_ctx.set({"session_id": session_id, "correlation_id": correlation_id})
    _otel_by_span_id.set({})


def drain_pending_spans() -> list[ExecutionSpan]:
    pending = list(_pending_list())
    _pending_spans.set([])
    return pending


def start_span(
    span_type: SpanType,
    *,
    runtime_state: str = "",
    parent_span_id: str | None = None,
    metadata: dict | None = None,
) -> ExecutionSpan:
    ctx = _session_context()
    session_id = ctx.get("session_id", "")
    correlation_id = ctx.get("correlation_id", "")
    trace_id = trace_id_from_correlation(correlation_id) if correlation_id else ""

    parents = _parents_map()
    if parent_span_id is None and span_type != SpanType.ORCHESTRATION:
        if span_type == SpanType.TRANSITION:
            parent_span_id = parents.get(SpanType.ORCHESTRATION)
        elif span_type in (SpanType.TOOL_EXECUTION, SpanType.CONTEXT_BUILD, SpanType.AGENT_REASONING):
            parent_span_id = parents.get(SpanType.ORCHESTRATION)
        elif span_type == SpanType.RETRY:
            parent_span_id = parents.get(SpanType.AGENT_REASONING)
        elif span_type == SpanType.REPLAY:
            parent_span_id = parents.get(SpanType.ORCHESTRATION)
        elif span_type == SpanType.APPROVAL:
            parent_span_id = parents.get(SpanType.ORCHESTRATION)

    span = ExecutionSpan(
        span_id=str(uuid4()),
        trace_id=trace_id,
        correlation_id=correlation_id,
        session_id=session_id,
        parent_span_id=parent_span_id,
        span_type=span_type,
        runtime_state=runtime_state,
        metadata=metadata or {},
    )
    pending = _pending_list()
    pending.append(span)

    if span_type == SpanType.ORCHESTRATION:
        parents[SpanType.ORCHESTRATION] = span.span_id

    otel_span = start_otel_span(
        f"runtime.{span_type.value}",
        trace_id=trace_id,
        attributes={
            "span_id": span.span_id,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "span_type": span_type.value,
        },
    )
    if otel_span is not None:
        _otel_map()[span.span_id] = otel_span
    return span


def end_span(
    span: ExecutionSpan,
    *,
    status: SpanStatus = SpanStatus.OK,
    metadata: dict | None = None,
) -> ExecutionSpan:
    span.completed_at = datetime.now(timezone.utc)
    span.status = status
    if metadata:
        span.metadata.update(metadata)
    pending = _pending_list()
    for i, s in enumerate(pending):
        if s.span_id == span.span_id:
            pending[i] = span
            break
    otel_span = _otel_map().pop(span.span_id, None)
    if otel_span is not None:
        end_otel_span(otel_span, ok=status == SpanStatus.OK)
    return span


class ExecutionSpanManager:
    """Thin facade used by orchestrator."""

    def begin_session(self, *, session_id: str, correlation_id: str) -> None:
        begin_session(session_id=session_id, correlation_id=correlation_id)

    def start(self, span_type: SpanType, **kwargs: Any) -> ExecutionSpan:
        return start_span(span_type, **kwargs)

    def end(self, span: ExecutionSpan, **kwargs: Any) -> ExecutionSpan:
        return end_span(span, **kwargs)

    def drain(self) -> list[ExecutionSpan]:
        return drain_pending_spans()


span_manager = ExecutionSpanManager()
