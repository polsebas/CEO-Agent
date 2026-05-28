"""Replay-aware governance — escalation only, never relax approvals."""

from __future__ import annotations

from core.config import settings
from core.replay_policy import replay_cognition_relaxation, replay_governance_pressure
from schemas.adaptive import AdaptivePolicy, AdaptiveSignals
from schemas.diagnostics import ReplayAnalytics
from schemas.governance_runtime import AdaptiveGovernanceEvent, GovernanceAction


class AdaptiveGovernanceService:
    def apply_replay_to_signals(
        self,
        signals: AdaptiveSignals,
        analytics: ReplayAnalytics,
    ) -> AdaptiveSignals:
        gov_pressure = replay_governance_pressure(analytics)
        return signals.model_copy(
            update={
                "governance_pressure": max(signals.governance_pressure, gov_pressure),
                "replay_confidence": analytics.replay_confidence,
                "drift_severity": analytics.drift_severity,
            }
        )

    def events_from_analytics(
        self,
        analytics: ReplayAnalytics,
    ) -> list[AdaptiveGovernanceEvent]:
        events: list[AdaptiveGovernanceEvent] = []
        if replay_governance_pressure(analytics) >= 0.5:
            events.append(
                AdaptiveGovernanceEvent(
                    session_id=analytics.session_id,
                    correlation_id=analytics.correlation_id,
                    action=GovernanceAction.REPLAY_DRIFT_DETECTED,
                    approval_bias_delta=min(
                        settings.adaptive_approval_bias_max,
                        1.0,
                    ),
                    metadata={"drift_fields": analytics.drift_fields},
                )
            )
            events.append(
                AdaptiveGovernanceEvent(
                    session_id=analytics.session_id,
                    correlation_id=analytics.correlation_id,
                    action=GovernanceAction.FORCE_DETERMINISTIC,
                )
            )
            events.append(
                AdaptiveGovernanceEvent(
                    session_id=analytics.session_id,
                    correlation_id=analytics.correlation_id,
                    action=GovernanceAction.DISABLE_DELEGATION,
                )
            )
        return events

    def adjust_policy_cognition_only(
        self,
        policy: AdaptivePolicy,
        analytics: ReplayAnalytics,
    ) -> AdaptivePolicy:
        """Stable replay may slightly relax context budget — never approval bias."""
        relaxation = replay_cognition_relaxation(analytics)
        if relaxation > 0:
            policy = policy.model_copy(
                update={
                    "context_budget_ratio": min(
                        settings.adaptive_context_budget_relaxed_max,
                        policy.context_budget_ratio + relaxation,
                    ),
                }
            )
        return policy

    def effective_approval_delta(self, policy: AdaptivePolicy) -> int:
        """Only non-negative escalation bias."""
        return max(0, int(round(policy.approval_escalation_bias)))


adaptive_governance_service = AdaptiveGovernanceService()
