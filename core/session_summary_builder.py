"""Human-readable operational summaries from diagnostics snapshots."""

from __future__ import annotations

from schemas.diagnostics import ReplayAnalytics, SessionDiagnostics
from schemas.session_summary import HumanSummaryLine
from schemas.tools import ToolReliabilityProfile


def build_human_summaries(
    diagnostics: SessionDiagnostics,
    *,
    replay_analytics: ReplayAnalytics | None = None,
    unstable_tools: list[ToolReliabilityProfile] | None = None,
) -> list[HumanSummaryLine]:
    lines: list[HumanSummaryLine] = []

    health = diagnostics.runtime_health
    if health and health.degraded_mode_active:
        reason = "retry pressure" if health.retry_pressure > 0.5 else "runtime health degradation"
        if diagnostics.telemetry_summary.get("total_retries", 0) >= 3:
            reason = "retry storm"
        lines.append(
            HumanSummaryLine(
                severity="critical",
                headline=f"Session entered degraded mode due to {reason}",
                detail=f"Health band: {health.health_band.value}, replay confidence {health.replay_confidence:.2f}",
                source="degraded_mode",
            )
        )

    policy = diagnostics.adaptive_policy_summary or {}
    if policy.get("delegation_enabled") is False:
        lines.append(
            HumanSummaryLine(
                severity="warning",
                headline="Delegation frozen because adaptive policy restricted delegation",
                detail="delegation_enabled=false in current adaptive policy",
                source="delegation_frozen",
            )
        )
    if policy.get("max_retry_depth") == 1 and diagnostics.telemetry_summary.get("total_retries", 0) > 0:
        lines.append(
            HumanSummaryLine(
                severity="warning",
                headline="Retry depth capped after retry storm detection",
                detail=f"max_retry_depth={policy.get('max_retry_depth')}",
                source="retry_storm",
            )
        )

    if replay_analytics and replay_analytics.drift_severity > 0:
        lines.append(
            HumanSummaryLine(
                severity="warning" if replay_analytics.drift_severity < 0.5 else "critical",
                headline="Replay drift detected across runtime snapshots",
                detail=f"Drift severity {replay_analytics.drift_severity:.2f}, fields: {', '.join(replay_analytics.drift_fields) or 'n/a'}",
                source="replay_drift",
            )
        )
    elif health and health.replay_confidence < 0.85:
        lines.append(
            HumanSummaryLine(
                severity="warning",
                headline="Replay confidence dropped below operational threshold",
                detail=f"Current replay confidence: {health.replay_confidence:.2f}",
                source="replay_confidence",
            )
        )

    avg_pressure = diagnostics.telemetry_summary.get("avg_context_pressure", 0.0)
    if avg_pressure > 0.7:
        lines.append(
            HumanSummaryLine(
                severity="warning",
                headline="Context compressed under high pressure",
                detail=f"Average context pressure: {avg_pressure:.2f}",
                source="context_pressure",
            )
        )

    for anomaly in diagnostics.anomaly_events:
        lines.append(
            HumanSummaryLine(
                severity=anomaly.severity.value if anomaly.severity.value in ("low", "medium") else "critical",
                headline=f"Runtime anomaly: {anomaly.anomaly_type.replace('_', ' ')}",
                detail=str(anomaly.metadata) if anomaly.metadata else None,
                source="anomaly",
            )
        )

    for event in diagnostics.stability_summary.get("events", []):
        event_type = event.get("event_type", "stability_event")
        if "retry" in event_type.lower():
            lines.append(
                HumanSummaryLine(
                    severity="warning",
                    headline="Stability event: retry storm pattern detected",
                    detail=event_type,
                    source="retry_storm",
                )
            )

    for event in diagnostics.governance_summary.get("events", []):
        action = event.get("action", "")
        if action == "disable_delegation":
            lines.append(
                HumanSummaryLine(
                    severity="warning",
                    headline="Governance escalated: delegation disabled",
                    detail=str(event.get("metadata", {})),
                    source="governance",
                )
            )
        elif action == "escalate_approval":
            lines.append(
                HumanSummaryLine(
                    severity="info",
                    headline="Governance escalated approval requirements",
                    detail=str(event.get("metadata", {})),
                    source="governance",
                )
            )

    if unstable_tools:
        for tool in unstable_tools:
            if tool.routing_band.value == "degraded" or tool.success_rate < 0.8:
                lines.append(
                    HumanSummaryLine(
                        severity="warning",
                        headline=f"Tool {tool.tool_name} marked unstable",
                        detail=f"Success rate {tool.success_rate:.0%}, band {tool.routing_band.value}",
                        source="tool_unstable",
                    )
                )

    if not lines and health:
        lines.append(
            HumanSummaryLine(
                severity="info",
                headline="Session operating within normal parameters",
                detail=f"Health band: {health.health_band.value}",
                source="healthy",
            )
        )

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    lines.sort(key=lambda x: severity_order.get(x.severity, 3))
    return lines
