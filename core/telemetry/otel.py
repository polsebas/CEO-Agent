"""OpenTelemetry provider — traces, OTLP export, Prometheus metrics."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from core.canonical import stable_hash
from core.config import settings

if TYPE_CHECKING:
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import Tracer

_initialized = False
_tracer: Tracer | None = None
_meter: Meter | None = None
_prometheus_reader = None

_cognitive_tokens = None
_reasoning_latency = None
_retry_count = None
_runtime_health_score = None


def trace_id_from_correlation(correlation_id: str) -> str:
    return stable_hash({"correlation_id": correlation_id})


def init_telemetry() -> None:
    global _initialized, _tracer, _meter, _prometheus_reader
    global _cognitive_tokens, _reasoning_latency, _retry_count, _runtime_health_score

    if _initialized:
        return

    disabled = settings.otel_sdk_disabled or os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true"
    if disabled or not settings.telemetry_enabled:
        _initialized = True
        return

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name or os.environ.get(
                "OTEL_SERVICE_NAME", "ceo-agent"
            ),
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    endpoint = settings.otel_exporter_otlp_endpoint or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", ""
    )
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("ceo-agent.runtime")

    _prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[_prometheus_reader])
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter("ceo-agent.runtime")

    _cognitive_tokens = _meter.create_counter(
        "cognitive_tokens_total",
        description="Estimated cognitive tokens consumed",
    )
    _reasoning_latency = _meter.create_histogram(
        "reasoning_latency_ms",
        description="Agent reasoning latency milliseconds",
    )
    _retry_count = _meter.create_counter(
        "retry_count",
        description="Structured retry events",
    )
    _runtime_health_score = _meter.create_up_down_counter(
        "runtime_health_score",
        description="Composite runtime health score",
    )

    _initialized = True


def shutdown_telemetry() -> None:
    global _initialized, _tracer, _meter, _prometheus_reader
    global _cognitive_tokens, _reasoning_latency, _retry_count, _runtime_health_score
    if not _initialized:
        return
    try:
        from opentelemetry import metrics, trace

        tp = trace.get_tracer_provider()
        if hasattr(tp, "shutdown"):
            tp.shutdown()
        mp = metrics.get_meter_provider()
        if hasattr(mp, "shutdown"):
            mp.shutdown()
    except Exception:
        pass
    try:
        import opentelemetry.metrics._internal as metrics_internal
        import opentelemetry.trace as trace_module
        from opentelemetry.util._once import Once

        trace_module._TRACER_PROVIDER = None
        trace_module._TRACER_PROVIDER_SET_ONCE = Once()
        metrics_internal._METER_PROVIDER = None
        metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    except Exception:
        pass
    _initialized = False
    _tracer = None
    _meter = None
    _prometheus_reader = None
    _cognitive_tokens = None
    _reasoning_latency = None
    _retry_count = None
    _runtime_health_score = None


def get_tracer():
    init_telemetry()
    if _tracer is not None:
        return _tracer
    from opentelemetry import trace

    return trace.get_tracer("ceo-agent.noop")


def get_meter():
    init_telemetry()
    if _meter is not None:
        return _meter
    from opentelemetry import metrics

    return metrics.get_meter("ceo-agent.noop")


def record_cognitive_metrics(
    *,
    agent_id: str,
    session_id: str,
    token_estimate: int,
    reasoning_latency_ms: int,
    retry_count: int,
) -> None:
    init_telemetry()
    labels = {"agent_id": agent_id, "session_id": session_id}
    if _cognitive_tokens is not None:
        _cognitive_tokens.add(token_estimate, labels)
    if _reasoning_latency is not None:
        _reasoning_latency.record(reasoning_latency_ms, labels)
    if _retry_count is not None:
        _retry_count.add(retry_count, labels)


def record_health_score(score: float, session_id: str) -> None:
    init_telemetry()
    if _runtime_health_score is not None:
        _runtime_health_score.add(int(score * 100), {"session_id": session_id})


def start_otel_span(name: str, *, trace_id: str, attributes: dict | None = None):
    if settings.otel_sdk_disabled or not settings.telemetry_enabled:
        return None
    tracer = get_tracer()
    span = tracer.start_span(name)
    if attributes:
        for k, v in attributes.items():
            span.set_attribute(k, v)
    span.set_attribute("trace_id", trace_id)
    return span


def end_otel_span(otel_span: Any, *, ok: bool = True) -> None:
    if otel_span is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        if not ok:
            otel_span.set_status(Status(StatusCode.ERROR))
        otel_span.end()
    except Exception:
        pass


def get_prometheus_metrics_text() -> str:
    """OTel metrics via PrometheusMetricReader + prometheus_client REGISTRY."""
    from prometheus_client import REGISTRY, generate_latest

    init_telemetry()
    if _prometheus_reader is not None:
        try:
            _prometheus_reader.collect()
        except Exception:
            pass
    return generate_latest(REGISTRY).decode("utf-8")
