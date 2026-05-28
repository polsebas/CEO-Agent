"""Replay-aware policy pressure (observational inputs only)."""

from __future__ import annotations

from schemas.diagnostics import ReplayAnalytics


def replay_governance_pressure(analytics: ReplayAnalytics) -> float:
    if analytics.drift_severity >= 0.5 or analytics.replay_confidence < 0.5:
        return min(1.0, analytics.drift_severity + (1.0 - analytics.replay_confidence) * 0.5)
    return 0.0


def replay_cognition_relaxation(analytics: ReplayAnalytics) -> float:
    """Stable replay may relax cognition budget only — never governance."""
    if analytics.outcome_match and analytics.replay_confidence >= 0.9 and analytics.drift_severity < 0.1:
        return 0.05
    return 0.0
