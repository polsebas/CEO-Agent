"""Presentation helpers for human summary lines."""

from __future__ import annotations

from schemas.session_summary import HumanSummaryLine

_BADGE_CLASS = {
    "critical": "badge-error",
    "warning": "badge-warning",
    "info": "badge-info",
    "low": "badge-ghost",
    "medium": "badge-warning",
    "high": "badge-error",
}


def badge_class(line: HumanSummaryLine) -> str:
    return _BADGE_CLASS.get(line.severity, "badge-ghost")


def icon_char(line: HumanSummaryLine) -> str:
    mapping = {
        "degraded_mode": "⚠",
        "retry_storm": "↻",
        "delegation_frozen": "⏸",
        "replay_drift": "≠",
        "replay_confidence": "◎",
        "context_pressure": "▤",
        "tool_unstable": "🔧",
        "governance": "⚖",
        "anomaly": "!",
        "healthy": "✓",
    }
    return mapping.get(line.source, "•")
