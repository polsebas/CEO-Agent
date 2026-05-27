"""OpenTelemetry bootstrap for RRM-2."""

from core.telemetry.otel import get_meter, get_tracer, init_telemetry, shutdown_telemetry

__all__ = ["init_telemetry", "shutdown_telemetry", "get_tracer", "get_meter"]
