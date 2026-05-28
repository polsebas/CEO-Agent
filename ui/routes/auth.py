"""Login/logout for MVP UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from api.auth import _encode_token
from core.roles import UserRole
from ui.deps import COOKIE_NAME, require_ui_auth
from ui.templates_env import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "roles": [r.value for r in UserRole]},
    )


@router.post("/login")
async def login_submit(
    response: Response,
    user_id: Annotated[str, Form()] = "demo-user",
    role: Annotated[str, Form()] = "operator",
):
    try:
        user_role = UserRole(role)
    except ValueError:
        user_role = UserRole.OPERATOR
    token = _encode_token(user_id, user_role)
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=86400)
    return redirect


@router.post("/logout")
async def logout():
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(COOKIE_NAME)
    return redirect
