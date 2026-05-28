"""UI route modules."""

from __future__ import annotations

from fastapi import APIRouter

from ui.routes import adaptive, approvals, auth, dashboard, diagnostics, replay, sessions

router = APIRouter(include_in_schema=False)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(sessions.router)
router.include_router(replay.router)
router.include_router(diagnostics.router)
router.include_router(adaptive.router)
router.include_router(approvals.router)
