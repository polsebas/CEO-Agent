"""Approvals console UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.auth import AuthContext
from core.approval_service import execute_approved_action_in_session
from core.permissions import Permission
from core.policy import policy_engine
from core.rbac import can_approve_level, role_has_permission
from ui.deps import nav_items, require_ui_auth
from ui.services.human_labels import badge_class, icon_char
from ui.services.query_facade import ui_query_facade
from ui.templates_env import templates

router = APIRouter()


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_page(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
):
    cards = await ui_query_facade.get_approval_queue(auth=auth)
    can_approve = role_has_permission(auth.role, Permission.ACTION_APPROVE)
    return templates.TemplateResponse(
        request,
        "approvals.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "cards": cards,
            "can_approve": can_approve,
            "badge_class": badge_class,
            "icon_char": icon_char,
        },
    )


@router.post("/ui/approvals/{approval_id}/approve")
async def approve_htmx(
    approval_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    session_id: Annotated[str | None, Form()] = None,
):
    if not role_has_permission(auth.role, Permission.ACTION_APPROVE):
        return RedirectResponse("/approvals", status_code=303)
    approval = await policy_engine.get_approval(approval_id)
    if not approval or not can_approve_level(auth.role, approval.risk_level):
        return RedirectResponse("/approvals", status_code=303)
    await execute_approved_action_in_session(
        approval_id,
        approved_by=auth.user_id,
        session_id=session_id or approval.correlation_id,
    )
    return RedirectResponse("/approvals", status_code=303)
