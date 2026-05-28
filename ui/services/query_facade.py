"""Single read facade for MVP UI — no HTTP loopback to /api/v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from api.auth import AuthContext
from core.adaptive_governance import adaptive_governance_service
from core.diagnostics import diagnostics_service
from core.persistence import (
    query_adaptive_policy,
    query_context_intelligence,
    query_governance_events,
    query_stability_events,
    query_tool_reliability_profiles,
)
from core.permissions import Permission
from core.policy import policy_engine
from core.rbac import role_has_permission
from core.replay import replay_engine
from core.replay_analytics import analyze_replay
from core.session_list import list_session_summaries
from core.session_summary_builder import build_human_summaries
from core.timeline import build_executive_timeline
from schemas.adaptive import AdaptivePolicy
from schemas.diagnostics import ReplayAnalytics, SessionDiagnostics
from schemas.runtime import ReplayMode
from schemas.session_summary import HumanSummaryLine, SessionListFilters, SessionSummary


@dataclass
class UnifiedTimelineEvent:
    timestamp: datetime
    event_type: str
    headline: str
    detail: str | None = None
    metadata: dict = field(default_factory=dict)
    severity: str = "info"


@dataclass
class SessionDetailState:
    summary: SessionSummary
    diagnostics: SessionDiagnostics
    human_summaries: list[HumanSummaryLine]
    replay_analytics: ReplayAnalytics | None = None


@dataclass
class DashboardState:
    recent_sessions: list[SessionSummary]
    degraded_sessions: list[SessionSummary]
    pending_approvals: list[dict]
    tool_warnings: list[dict]
    runtime_healthy: bool
    pending_count: int


@dataclass
class ReplayUIState:
    analytics: ReplayAnalytics
    governance_events: list[dict]
    approval_escalation_delta: float
    replay_session: dict | None = None
    mode: str = "frozen"


@dataclass
class ApprovalCardState:
    approval: dict
    session_id: str | None
    human_context: list[HumanSummaryLine]


class UIQueryFacade:
    async def list_sessions(
        self,
        *,
        filters: SessionListFilters | None = None,
        auth: AuthContext,
    ) -> list[SessionSummary]:
        self._require(auth, Permission.SESSION_READ)
        return await list_session_summaries(filters)

    async def get_session_detail(
        self,
        session_id: str,
        correlation_id: str,
        *,
        auth: AuthContext,
    ) -> SessionDetailState:
        self._require(auth, Permission.DIAGNOSTICS_READ)
        diagnostics = await diagnostics_service.get_diagnostics(session_id, correlation_id)
        replay_analytics = await diagnostics_service.get_replay_analysis(
            session_id, correlation_id, mode=ReplayMode.FROZEN
        )
        unstable = await self._unstable_tools()
        human = build_human_summaries(
            diagnostics,
            replay_analytics=replay_analytics,
            unstable_tools=unstable,
        )
        summaries = await list_session_summaries(SessionListFilters(limit=500))
        summary = next((s for s in summaries if s.session_id == session_id), None)
        if summary is None:
            health = diagnostics.runtime_health
            summary = SessionSummary(
                session_id=session_id,
                correlation_id=correlation_id,
                health_status=health.health_band.value if health else "healthy",
                degraded=health.degraded_mode_active if health else False,
                replay_confidence=health.replay_confidence if health else replay_analytics.replay_confidence,
            )
        return SessionDetailState(
            summary=summary,
            diagnostics=diagnostics,
            human_summaries=human,
            replay_analytics=replay_analytics,
        )

    async def get_dashboard_state(self, *, auth: AuthContext) -> DashboardState:
        self._require(auth, Permission.SESSION_READ)
        all_sessions = await list_session_summaries(SessionListFilters(limit=100))
        degraded = [s for s in all_sessions if s.degraded]
        pending = await policy_engine.list_pending_approvals()
        pending_dicts = [a.model_dump() for a in pending]
        profiles = await query_tool_reliability_profiles()
        tool_warnings = [
            p.model_dump()
            for p in profiles
            if p.routing_band.value == "degraded" or p.success_rate < 0.85
        ]
        from core.persistence import health_check_db

        db_ok = await health_check_db()
        return DashboardState(
            recent_sessions=all_sessions[:10],
            degraded_sessions=degraded[:10],
            pending_approvals=pending_dicts,
            tool_warnings=tool_warnings,
            runtime_healthy=db_ok,
            pending_count=len(pending_dicts),
        )

    async def get_timeline_events(
        self,
        session_id: str,
        correlation_id: str,
        *,
        auth: AuthContext,
    ) -> list[UnifiedTimelineEvent]:
        self._require(auth, Permission.TIMELINE_READ)
        events: list[UnifiedTimelineEvent] = []

        exec_timeline = await build_executive_timeline(correlation_id)
        for entry in exec_timeline:
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            events.append(
                UnifiedTimelineEvent(
                    timestamp=ts,
                    event_type=entry.get("type", "event"),
                    headline=entry.get("message", ""),
                    metadata=entry.get("metadata") or {},
                    severity=self._severity_for_type(entry.get("type", "")),
                )
            )

        if role_has_permission(auth.role, Permission.DIAGNOSTICS_READ):
            diagnostics = await diagnostics_service.get_diagnostics(session_id, correlation_id)
            for anomaly in diagnostics.anomaly_events:
                events.append(
                    UnifiedTimelineEvent(
                        timestamp=anomaly.detected_at,
                        event_type="anomaly",
                        headline=f"Anomaly: {anomaly.anomaly_type}",
                        detail=f"Severity {anomaly.severity.value}",
                        metadata=anomaly.metadata,
                        severity=anomaly.severity.value if anomaly.severity.value != "low" else "warning",
                    )
                )
            for raw in diagnostics.stability_summary.get("events", []):
                created = raw.get("created_at")
                ts = (
                    datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if isinstance(created, str)
                    else datetime.now(timezone.utc)
                )
                events.append(
                    UnifiedTimelineEvent(
                        timestamp=ts,
                        event_type="stability",
                        headline=f"Stability: {raw.get('event_type', 'event')}",
                        metadata=raw,
                        severity=raw.get("severity", "medium"),
                    )
                )
            for raw in diagnostics.governance_summary.get("events", []):
                created = raw.get("created_at")
                ts = (
                    datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if isinstance(created, str)
                    else datetime.now(timezone.utc)
                )
                events.append(
                    UnifiedTimelineEvent(
                        timestamp=ts,
                        event_type="governance",
                        headline=f"Governance: {raw.get('action', 'event')}",
                        metadata=raw,
                        severity="warning",
                    )
                )

            span_tree = await diagnostics_service.get_spans(session_id, correlation_id=correlation_id)
            for span in span_tree.get("spans", []):
                started = span.get("started_at")
                if not started:
                    continue
                ts = (
                    datetime.fromisoformat(started.replace("Z", "+00:00"))
                    if isinstance(started, str)
                    else datetime.now(timezone.utc)
                )
                span_type = span.get("span_type", "span")
                events.append(
                    UnifiedTimelineEvent(
                        timestamp=ts,
                        event_type="span",
                        headline=f"Span {span_type}: {span.get('runtime_state', '')}",
                        metadata={"span_id": span.get("span_id"), "status": span.get("status")},
                        severity="info",
                    )
                )

        events.sort(key=lambda e: e.timestamp)
        return events

    async def get_replay_state(
        self,
        session_id: str,
        correlation_id: str,
        *,
        auth: AuthContext,
        mode: ReplayMode = ReplayMode.FROZEN,
    ) -> ReplayUIState:
        self._require(auth, Permission.DIAGNOSTICS_READ)
        analytics = await analyze_replay(session_id, correlation_id, mode=mode)
        events = await query_governance_events(session_id)
        snap = await query_adaptive_policy(session_id)
        policy = snap.policy if snap else AdaptivePolicy()
        replay_session = None
        if role_has_permission(auth.role, Permission.REPLAY_EXECUTE):
            session = await replay_engine.replay_session(session_id, correlation_id, mode)
            replay_session = session.model_dump()
        return ReplayUIState(
            analytics=analytics,
            governance_events=[e.model_dump() for e in events],
            approval_escalation_delta=adaptive_governance_service.effective_approval_delta(policy),
            replay_session=replay_session,
            mode=mode.value,
        )

    async def get_adaptive_state(self, session_id: str, *, auth: AuthContext) -> dict[str, Any]:
        self._require(auth, Permission.DIAGNOSTICS_READ)
        snap = await query_adaptive_policy(session_id)
        stability = await query_stability_events(session_id)
        context = await query_context_intelligence(session_id)
        score = 1.0
        if stability:
            severities = {"low": 0.1, "medium": 0.2, "high": 0.35, "critical": 0.5}
            penalty = sum(severities.get(e.severity, 0.2) for e in stability)
            score = max(0.0, 1.0 - min(1.0, penalty))
        return {
            "policy": snap.model_dump() if snap else None,
            "stability_score": round(score, 4),
            "stability_events": [e.model_dump() for e in stability],
            "context_intelligence": context,
        }

    async def get_diagnostics_detail(
        self,
        session_id: str,
        correlation_id: str,
        *,
        auth: AuthContext,
    ) -> dict[str, Any]:
        self._require(auth, Permission.DIAGNOSTICS_READ)
        detail = await self.get_session_detail(session_id, correlation_id, auth=auth)
        spans = await diagnostics_service.get_spans(session_id, correlation_id=correlation_id)
        telemetry = await diagnostics_service.get_telemetry(session_id, correlation_id=correlation_id)
        context = await diagnostics_service.get_context(session_id)
        health = await diagnostics_service.get_health(session_id)
        return {
            "diagnostics": detail.diagnostics.model_dump(),
            "human_summaries": [h.model_dump() for h in detail.human_summaries],
            "spans": spans,
            "telemetry": telemetry,
            "context": context,
            "health": health,
        }

    async def get_approval_queue(self, *, auth: AuthContext) -> list[ApprovalCardState]:
        self._require(auth, Permission.APPROVALS_READ)
        pending = await policy_engine.list_pending_approvals()
        all_sessions = await list_session_summaries(SessionListFilters(limit=500))
        corr_to_session = {s.correlation_id: s.session_id for s in all_sessions}
        cards: list[ApprovalCardState] = []
        for approval in pending:
            human: list[HumanSummaryLine] = []
            sid = corr_to_session.get(approval.correlation_id, approval.correlation_id)
            try:
                detail = await self.get_session_detail(sid, approval.correlation_id, auth=auth)
                human = detail.human_summaries[:3]
            except Exception:
                pass
            cards.append(
                ApprovalCardState(
                    approval=approval.model_dump(),
                    session_id=sid,
                    human_context=human,
                )
            )
        return cards

    async def build_session_bundle(
        self,
        session_id: str,
        correlation_id: str,
        *,
        auth: AuthContext,
    ) -> dict[str, Any]:
        self._require(auth, Permission.DIAGNOSTICS_READ)
        detail = await self.get_session_detail(session_id, correlation_id, auth=auth)
        timeline = await self.get_timeline_events(session_id, correlation_id, auth=auth)
        replay = await self.get_replay_state(session_id, correlation_id, auth=auth)
        adaptive = await self.get_adaptive_state(session_id, auth=auth)
        return {
            "session_id": session_id,
            "correlation_id": correlation_id,
            "diagnostics": detail.diagnostics.model_dump(),
            "replay_analysis": replay.analytics.model_dump(),
            "adaptive_policy": adaptive.get("policy"),
            "timeline": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "headline": e.headline,
                    "detail": e.detail,
                    "metadata": e.metadata,
                }
                for e in timeline
            ],
            "human_summaries": [h.model_dump() for h in detail.human_summaries],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _unstable_tools(self):
        profiles = await query_tool_reliability_profiles()
        return [p for p in profiles if p.routing_band.value == "degraded" or p.success_rate < 0.85]

    @staticmethod
    def _require(auth: AuthContext, permission: Permission) -> None:
        if not role_has_permission(auth.role, permission):
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )

    @staticmethod
    def _severity_for_type(entry_type: str) -> str:
        if entry_type in ("approval", "side_effect"):
            return "warning"
        if entry_type == "outcome":
            return "info"
        return "info"


ui_query_facade = UIQueryFacade()
