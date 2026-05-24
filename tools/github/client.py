"""GitHub tools with MCP attempt and stub fallback."""

from __future__ import annotations

import httpx

from core.config import settings
from core.mcp_security import MCPValidationError, validate_mcp_response, validate_mcp_url
from core.persistence import get_world_state


async def _github_mcp_call(method: str, params: dict) -> dict | None:
    try:
        validate_mcp_url(settings.github_mcp_url)
    except MCPValidationError:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.mcp_timeout_seconds) as client:
            response = await client.post(
                f"{settings.github_mcp_url}/tools/{method}",
                json=params,
            )
            if response.status_code == 200:
                payload = response.json()
                return validate_mcp_response(payload)
    except Exception:
        return None
    return None


async def list_github_prs(status: str = "open", repo: str | None = None) -> dict:
    repo = repo or settings.github_repo
    mcp_result = await _github_mcp_call("list_prs", {"repo": repo, "status": status})
    if mcp_result:
        return {"source": "github_mcp", **mcp_result}
    return {
        "source": "stub",
        "repo": repo,
        "status": status,
        "open_count": 7,
        "blocked_count": 2,
        "prs": [
            {"number": 142, "title": "Fix auth middleware", "blocked": True},
            {"number": 141, "title": "Add rate limiting", "blocked": False},
        ],
    }


async def get_repo_health(repo: str | None = None) -> dict:
    repo = repo or settings.github_repo
    mcp_result = await _github_mcp_call("repo_health", {"repo": repo})
    if mcp_result:
        return {"source": "github_mcp", **mcp_result}
    ws = get_world_state()
    degraded = any(d.status == "degraded" for d in ws.active_deployments)
    return {
        "source": "stub",
        "repo": repo,
        "health": "degraded" if degraded else "healthy",
        "open_issues": 12,
        "last_deploy": ws.active_deployments[0].version if ws.active_deployments else "unknown",
        "ci_status": "failing" if degraded else "passing",
    }


async def analyze_incidents() -> dict:
    ws = get_world_state()
    return {
        "incidents": [i.model_dump() for i in ws.active_incidents],
        "count": len(ws.active_incidents),
        "critical": sum(1 for i in ws.active_incidents if i.severity == "critical"),
    }


async def prioritize_bugs() -> dict:
    return {
        "priority_bugs": [
            {"id": "BUG-101", "title": "Auth token refresh failure", "priority": "P0"},
            {"id": "BUG-98", "title": "Webhook retry loop", "priority": "P1"},
        ]
    }
