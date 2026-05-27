"""In-memory store for RRM-2 intelligence tables (test + use_in_memory_store parity)."""

from __future__ import annotations

from schemas.cognition import CognitiveTelemetry, PromptLineage
from schemas.diagnostics import SessionDiagnostics
from schemas.runtime_health import RuntimeAnomaly, RuntimeHealth
from schemas.spans import ExecutionSpan

_in_memory_spans: list[ExecutionSpan] = []
_in_memory_telemetry: list[CognitiveTelemetry] = []
_in_memory_health: list[RuntimeHealth] = []
_in_memory_lineage: list[PromptLineage] = []
_in_memory_anomalies: list[RuntimeAnomaly] = []
_in_memory_session_diagnostics: dict[str, SessionDiagnostics] = {}
_in_memory_retry_traces: list[dict] = []


def append_spans(spans: list[ExecutionSpan]) -> None:
    by_id = {s.span_id: s for s in _in_memory_spans}
    for span in spans:
        by_id[span.span_id] = span
    _in_memory_spans.clear()
    _in_memory_spans.extend(by_id.values())


def append_telemetry(rows: list[CognitiveTelemetry]) -> None:
    _in_memory_telemetry.extend(rows)


def append_health(health: RuntimeHealth) -> None:
    _in_memory_health.append(health)


def replace_health(health: RuntimeHealth) -> None:
    global _in_memory_health
    _in_memory_health = [
        h
        for h in _in_memory_health
        if not (h.session_id == health.session_id and h.correlation_id == health.correlation_id)
    ]
    _in_memory_health.append(health)


def append_lineage(rows: list[PromptLineage]) -> None:
    _in_memory_lineage.extend(rows)


def append_anomalies(rows: list[RuntimeAnomaly]) -> None:
    _in_memory_anomalies.extend(rows)


def save_session_diagnostics(diag: SessionDiagnostics) -> None:
    _in_memory_session_diagnostics[diag.session_id] = diag


def append_retry_trace(data: dict) -> None:
    _in_memory_retry_traces.append(data)


def get_spans(session_id: str, *, correlation_id: str | None = None) -> list[ExecutionSpan]:
    rows = [s for s in _in_memory_spans if s.session_id == session_id]
    if correlation_id:
        rows = [s for s in rows if s.correlation_id == correlation_id]
    return sorted(rows, key=lambda s: s.started_at)


def get_telemetry(session_id: str, *, correlation_id: str | None = None) -> list[CognitiveTelemetry]:
    rows = [t for t in _in_memory_telemetry if t.session_id == session_id]
    if correlation_id:
        rows = [t for t in rows if t.correlation_id == correlation_id]
    return sorted(rows, key=lambda t: t.created_at)


def get_health_snapshots(session_id: str) -> list[RuntimeHealth]:
    return sorted(
        [h for h in _in_memory_health if h.session_id == session_id],
        key=lambda h: h.generated_at,
    )


def get_lineage(session_id: str) -> list[PromptLineage]:
    return [p for p in _in_memory_lineage if p.session_id == session_id]


def get_anomalies(session_id: str) -> list[RuntimeAnomaly]:
    return sorted(
        [a for a in _in_memory_anomalies if a.session_id == session_id],
        key=lambda a: a.detected_at,
    )


def get_session_diagnostics(session_id: str) -> SessionDiagnostics | None:
    return _in_memory_session_diagnostics.get(session_id)


def reset_intelligence_store() -> None:
    _in_memory_spans.clear()
    _in_memory_telemetry.clear()
    _in_memory_health.clear()
    _in_memory_lineage.clear()
    _in_memory_anomalies.clear()
    _in_memory_session_diagnostics.clear()
    _in_memory_retry_traces.clear()
