"""RRM-3 adaptive cognition read APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.auth import AuthContext
from core.adaptive_governance import adaptive_governance_service
from core.persistence import (
    query_adaptive_policy,
    query_context_intelligence,
    query_governance_events,
    query_stability_events,
    query_tool_reliability_profiles,
)
from core.permissions import Permission
from core.rbac import require_permission
from core.replay_analytics import analyze_replay
from schemas.adaptive import AdaptivePolicy
from schemas.runtime import ReplayMode

router = APIRouter(prefix="/api/v1", tags=["adaptive"])


@router.get("/sessions/{session_id}/adaptive-policy")
async def session_adaptive_policy(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    snap = await query_adaptive_policy(session_id)
    if not snap:
        return None
    return snap.model_dump()


@router.get("/tools/reliability")
async def tools_reliability(
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    profiles = await query_tool_reliability_profiles()
    return [p.model_dump() for p in profiles]


@router.get("/sessions/{session_id}/stability")
async def session_stability(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    events = await query_stability_events(session_id)
    score = 1.0
    if events:
        severities = {"low": 0.1, "medium": 0.2, "high": 0.35, "critical": 0.5}
        penalty = sum(severities.get(e.severity, 0.2) for e in events)
        score = max(0.0, 1.0 - min(1.0, penalty))
    return {
        "session_id": session_id,
        "stability_score": round(score, 4),
        "events": [e.model_dump() for e in events],
    }


@router.get("/sessions/{session_id}/context-intelligence")
async def session_context_intelligence(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    return await query_context_intelligence(session_id)


@router.get("/replay/{session_id}/governance")
async def replay_governance(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
    correlation_id: str = Query(...),
    mode: ReplayMode = Query(ReplayMode.FROZEN),
):
    analytics = await analyze_replay(session_id, correlation_id, mode=mode)
    events = await query_governance_events(session_id)
    snap = await query_adaptive_policy(session_id)
    policy = snap.policy if snap else AdaptivePolicy()
    return {
        "analytics": analytics.model_dump(),
        "governance_events": [e.model_dump() for e in events],
        "approval_escalation_delta": adaptive_governance_service.effective_approval_delta(policy),
    }
