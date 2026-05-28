"""Deterministic adaptive policy engine — derives policy, does not execute."""

from __future__ import annotations

from core.canonical import stable_hash
from core.config import settings
from schemas.adaptive import AdaptivePolicy, AdaptivePolicySnapshot, AdaptiveSignals
from schemas.runtime_health import HealthBand

POLICY_VERSION = "rrm3-v1"
BASE_MEMORY_BUDGET = 8000


def policy_hash(policy: AdaptivePolicy) -> str:
    return stable_hash({"version": POLICY_VERSION, "policy": policy.model_dump()})


def signals_hash(signals: AdaptiveSignals) -> str:
    return stable_hash(signals.model_dump(mode="json"))


class AdaptivePolicyEngine:
    """Same AdaptiveSignals → same AdaptivePolicy (invariant §1)."""

    def derive(self, signals: AdaptiveSignals) -> AdaptivePolicy:
        policy = AdaptivePolicy()
        s = settings

        if signals.retry_density >= s.adaptive_retry_density_high:
            policy.max_retry_depth = max(0, policy.max_retry_depth - 2)

        if (
            signals.replay_confidence < s.adaptive_replay_confidence_low
            or signals.drift_severity >= s.adaptive_drift_severity_high
        ):
            policy.deterministic_mode = True
            policy.delegation_enabled = False
            policy.approval_escalation_bias = min(
                s.adaptive_approval_bias_max,
                policy.approval_escalation_bias + 1.0,
            )

        if signals.context_pressure >= s.adaptive_context_pressure_high:
            policy.context_budget_ratio = max(
                s.adaptive_context_budget_min,
                policy.context_budget_ratio * 0.5,
            )

        if signals.health_band in (HealthBand.DEGRADED, HealthBand.CRITICAL) or signals.degraded_mode_active:
            policy.delegation_enabled = False
            policy.max_retry_depth = 0
            policy.deterministic_mode = True
            policy.context_budget_ratio = min(policy.context_budget_ratio, 0.5)

        if signals.latency_pressure >= s.adaptive_latency_pressure_high:
            policy.context_budget_ratio = max(
                s.adaptive_context_budget_min,
                policy.context_budget_ratio * 0.75,
            )
            policy.tool_parallelism_limit = 1

        if signals.session_age_seconds >= s.adaptive_session_age_long_seconds:
            policy.context_budget_ratio = max(
                s.adaptive_context_budget_min,
                policy.context_budget_ratio * 0.8,
            )

        if signals.stability_pressure >= 0.5:
            policy.deterministic_mode = True
            policy.delegation_enabled = False
            policy.max_retry_depth = 0

        if signals.governance_pressure >= 0.5:
            policy.approval_escalation_bias = min(
                s.adaptive_approval_bias_max,
                policy.approval_escalation_bias + 0.5,
            )
            policy.delegation_enabled = False

        if signals.tool_failure_rate > 0.5:
            policy.deterministic_mode = True
            policy.tool_parallelism_limit = 1

        policy.context_budget_ratio = max(
            s.adaptive_context_budget_min,
            min(s.adaptive_context_budget_relaxed_max, policy.context_budget_ratio),
        )
        policy.approval_escalation_bias = max(0.0, min(s.adaptive_approval_bias_max, policy.approval_escalation_bias))
        return policy

    def snapshot(self, signals: AdaptiveSignals, policy: AdaptivePolicy | None = None) -> AdaptivePolicySnapshot:
        resolved = policy if policy is not None else self.derive(signals)
        return AdaptivePolicySnapshot(
            session_id=signals.session_id,
            correlation_id=signals.correlation_id,
            policy=resolved,
            signals_hash=signals_hash(signals),
            policy_hash=policy_hash(resolved),
        )


adaptive_policy_engine = AdaptivePolicyEngine()
