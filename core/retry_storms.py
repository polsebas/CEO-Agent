"""Retry storm detection and mitigation signals."""

from __future__ import annotations

from core.config import settings


def retry_density(telemetry: list) -> float:
    if not telemetry:
        return 0.0
    total = sum(getattr(t, "retry_count", 0) for t in telemetry)
    return min(1.0, total / (len(telemetry) * 3))


def is_retry_storm(density: float) -> bool:
    return density >= settings.adaptive_retry_density_high


def storm_mitigation_pressure(density: float) -> float:
    if not is_retry_storm(density):
        return 0.0
    return min(1.0, density)
