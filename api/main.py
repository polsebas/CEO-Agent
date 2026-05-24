"""FastAPI application with auth, governance, and hardened endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from api.auth import AuthContext, UserRole, require_auth, require_role
from core.approval_service import create_immutable_proposal, execute_approved_action, prepare_approval
from core.config import settings
from core.orchestrator import manual_orchestrator
from core.persistence import get_pool, health_check_db
from core.policy import policy_engine
from core.preprocessor import preprocessor
from core.replay import replay_engine
from core.storage import get_agent_storage
from core.timeline import build_executive_timeline
from schemas.approvals import ActionProposal, ImmutableActionProposal
from schemas.runtime import ReplayMode
from tools.router import execute_tool


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.use_in_memory_store:
        await get_pool()
        get_agent_storage()
    yield


app = FastAPI(title="CEO-Agent Cognitive OS", version="0.2.0", lifespan=lifespan)


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
    auth: Annotated[AuthContext, Depends(require_role(UserRole.FOUNDER))],
):
    pre = preprocessor.process(body.message)
    if pre.tool_name and pre.tier.value in ("tier1_regex", "tier2_embedding"):
        if pre.tool_name.startswith("delegate_"):
            pass
        elif pre.tool_name in (
            "list_github_prs",
            "get_repo_health",
            "calculate_runway",
            "get_cashflow_summary",
            "read_kpi_dashboard",
            "detect_blockers",
            "get_analytics_summary",
        ):
            correlation_id = body.correlation_id or str(uuid4())
            agent = "cto" if "github" in pre.tool_name or "repo" in pre.tool_name else "ceo"
            result = await execute_tool(pre.tool_name, agent, correlation_id, pre.params)
            return {
                "mode": "deterministic",
                "tier": pre.tier.value,
                "correlation_id": correlation_id,
                "result": result.model_dump(),
            }

    result = await manual_orchestrator.run_founder_request(
        body.message,
        session_id=body.session_id,
        correlation_id=body.correlation_id,
    )
    return result


@app.post("/api/v1/actions/prepare")
async def prepare_action(
    body: PrepareRequest,
    auth: Annotated[AuthContext, Depends(require_role(UserRole.FOUNDER))],
):
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
        approval = await prepare_approval(proposal, requester_agent=body.agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return approval.model_dump()


@app.post("/api/v1/actions/approve/{approval_id}")
async def approve_action(
    approval_id: str,
    body: ApproveRequest,
    auth: Annotated[AuthContext, Depends(require_role(UserRole.FOUNDER))],
):
    approval = policy_engine.get_approval(approval_id)
    if not approval or approval.status.value != "pending":
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    policy_engine.approve(approval_id, auth.user_id)
    try:
        result = await execute_approved_action(approval, approved_by=auth.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get("/api/v1/approvals")
async def list_approvals(auth: Annotated[AuthContext, Depends(require_role(UserRole.READONLY))]):
    return [a.model_dump() for a in policy_engine.list_pending_approvals()]


@app.get("/api/v1/replay/{session_id}")
async def replay_session(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_role(UserRole.ADMIN))],
    correlation_id: str = Query(...),
    mode: ReplayMode = Query(ReplayMode.FROZEN),
):
    session = await replay_engine.replay_session(session_id, correlation_id, mode)
    return session.model_dump()


@app.get("/api/v1/timeline")
async def executive_timeline(
    auth: Annotated[AuthContext, Depends(require_role(UserRole.READONLY))],
    correlation_id: str = Query(...),
):
    return await build_executive_timeline(correlation_id)


@app.get("/api/v1/agents/health")
async def agents_health(auth: Annotated[AuthContext, Depends(require_role(UserRole.ADMIN))]):
    from core.health import agent_health_registry

    return {k: v.model_dump() for k, v in (await agent_health_registry.all_agents()).items()}


def create_playground_app():
    try:
        from agno.playground import Playground

        from agents.factory import create_ceo_agent, create_cto_agent

        return Playground(agents=[create_ceo_agent(), create_cto_agent()]).get_app()
    except Exception:
        return app


playground_app = create_playground_app()
