"""Diff between canonical replay outcomes (live drift detection)."""

from __future__ import annotations

from schemas.replay import CanonicalReplayOutcome


def diff_canonical_outcomes(
    expected: CanonicalReplayOutcome,
    actual: CanonicalReplayOutcome,
) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}
    for field in (
        "final_runtime_state",
        "tool_sequence",
        "decision_sequence",
        "side_effects",
        "approvals",
    ):
        exp = getattr(expected, field)
        act = getattr(actual, field)
        if exp != act:
            changes[field] = [str(exp), str(act)]
    return changes
