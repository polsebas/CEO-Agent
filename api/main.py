"""FastAPI application with auth, governance, and hardened endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.auth import AuthContext
from api.adaptive import router as adaptive_router
from api.diagnostics import router as diagnostics_router
from api.sessions import router as sessions_router
from core.approval_service import (
    create_immutable_proposal,
    execute_approved_action_in_session,
    prepare_approval_in_session,
)
from core.config import settings
from core.orchestrator import manual_orchestrator
from core.persistence import get_pool, health_check_db
from core.permissions import Permission
from core.policy import policy_engine
from core.preprocessor import preprocessor
from core.rbac import can_approve_level, require_permission
from core.replay import replay_engine
from core.storage import get_agent_storage
from core.timeline import build_executive_timeline
from schemas.runtime import ReplayMode


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.telemetry.otel import init_telemetry, shutdown_telemetry

    init_telemetry()
    if not settings.use_in_memory_store:
        await get_pool()
        get_agent_storage()
    yield
    shutdown_telemetry()


app = FastAPI(title="CEO-Agent Cognitive OS", version="0.5.0", lifespan=lifespan)
app.include_router(diagnostics_router)
app.include_router(adaptive_router)
app.include_router(sessions_router)

from ui.routes import router as ui_router

_UI_STATIC = Path(__file__).resolve().parent.parent / "ui" / "static"
app.mount("/static", StaticFiles(directory=str(_UI_STATIC)), name="static")
app.include_router(ui_router)


@app.get("/metrics")
async def metrics():
    from core.telemetry.otel import get_prometheus_metrics_text

    return Response(content=get_prometheus_metrics_text(), media_type="text/plain")


class FounderRequest(BaseModel):
    message: str
    session_id: str | None = None
    correlation_id: str | None = None


class PrepareRequest(BaseModel):
    correlation_id: str
    action: str
    parameters: dict = {}
    agent: str = "ceo"
    side_effect_level: str = "EXECUTE_SAFE"
    impact_summary: str
    approval_level: int = 2
    task_id: str | None = None


class ApproveRequest(BaseModel):
    approved_by: str = "founder"
    session_id: str | None = None


@app.get("/health")
async def health():
    db_ok = await health_check_db()
    storage = get_agent_storage()
    healthy = db_ok and (storage is not None or settings.use_in_memory_store)
    return {
        "status": "healthy" if healthy else "degraded",
        "database": db_ok,
        "storage": storage is not None or settings.use_in_memory_store,
        "environment": settings.app_env,
    }


@app.post("/api/v1/founder/request")
async def founder_request(
    body: FounderRequest,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.FOUNDER_REQUEST))],
):
    pre = preprocessor.process(body.message)
    preprocessor_hint = None
    if pre.tool_name and pre.tier.value in ("tier1_regex", "tier2_embedding"):
        if not pre.tool_name.startswith("delegate_") and pre.tool_name in (
            "list_github_prs",
            "get_repo_health",
            "calculate_runway",
            "get_cashflow_summary",
            "read_kpi_dashboard",
            "detect_blockers",
            "get_analytics_summary",
        ):
            agent = "cto" if "github" in pre.tool_name or "repo" in pre.tool_name else "ceo"
            preprocessor_hint = {
                "tool_name": pre.tool_name,
                "agent_id": agent,
                "params": pre.params,
                "tier": pre.tier.value,
            }

    result = await manual_orchestrator.run_founder_request(
        body.message,
        session_id=body.session_id,
        correlation_id=body.correlation_id,
        preprocessor_hint=preprocessor_hint,
    )
    if preprocessor_hint:
        result["mode"] = "deterministic"
        result["tier"] = preprocessor_hint.get("tier")
    return result


@app.post("/api/v1/actions/prepare")
async def prepare_action(
    body: PrepareRequest,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_PREPARE))],
):
    if not can_approve_level(auth.role, body.approval_level):
        raise HTTPException(status_code=403, detail="Insufficient approval level for prepare")
    proposal = create_immutable_proposal(
        correlation_id=body.correlation_id,
        action=body.action,
        parameters=body.parameters,
        agent=body.agent,
        side_effect_level=body.side_effect_level,
        impact_summary=body.impact_summary,
        proposed_by=auth.user_id,
        approval_level=body.approval_level,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        task_id=body.task_id,
    )
    try:
        approval = await prepare_approval_in_session(proposal, requester_agent=body.agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return approval.model_dump()


@app.post("/api/v1/actions/approve/{approval_id}")
async def approve_action(
    approval_id: str,
    body: ApproveRequest,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_APPROVE))],
):
    approval = await policy_engine.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if not can_approve_level(auth.role, approval.risk_level):
        raise HTTPException(status_code=403, detail=f"Role cannot approve level {approval.risk_level}")
    try:
        result = await execute_approved_action_in_session(
            approval_id,
            approved_by=auth.user_id,
            session_id=body.session_id or approval.correlation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get("/api/v1/approvals")
async def list_approvals(auth: Annotated[AuthContext, Depends(require_permission(Permission.APPROVALS_READ))]):
    pending = await policy_engine.list_pending_approvals()
    return [a.model_dump() for a in pending]


@app.get("/api/v1/replay/{session_id}")
async def replay_session(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.REPLAY_EXECUTE))],
    correlation_id: str = Query(...),
    mode: ReplayMode = Query(ReplayMode.FROZEN),
):
    session = await replay_engine.replay_session(session_id, correlation_id, mode)
    return session.model_dump()


@app.get("/api/v1/timeline")
async def executive_timeline(
    auth: Annotated[AuthContext, Depends(require_permission(Permission.TIMELINE_READ))],
    correlation_id: str = Query(...),
):
    return await build_executive_timeline(correlation_id)


@app.get("/api/v1/agents/health")
async def agents_health(auth: Annotated[AuthContext, Depends(require_permission(Permission.AGENTS_HEALTH))]):
    from core.health import agent_health_registry

    return {k: v.model_dump() for k, v in (await agent_health_registry.all_agents()).items()}


@app.get("/api/v1/sessions/{session_id}/context-metrics")
async def context_metrics(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.TIMELINE_READ))],
    correlation_id: str = Query(...),
):
    from core.persistence import get_replay_snapshots

    snaps = await get_replay_snapshots(session_id)
    metrics = [snap["context_fingerprint"] for snap in snaps if snap.get("context_fingerprint")]
    return {"session_id": session_id, "correlation_id": correlation_id, "fingerprints": metrics}


def create_playground_app():
    try:
        from agno.playground import Playground

        from agents.factory import create_ceo_agent, create_cto_agent

        return Playground(agents=[create_ceo_agent(), create_cto_agent()]).get_app()
    except Exception:
        return app


playground_app = create_playground_app()
