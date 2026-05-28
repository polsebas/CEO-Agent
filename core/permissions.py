"""Role permission definitions (no FastAPI dependencies)."""

from __future__ import annotations

from enum import Enum

from core.roles import UserRole


class Permission(str, Enum):
    FOUNDER_REQUEST = "founder:request"
    ACTION_PREPARE = "action:prepare"
    ACTION_APPROVE = "action:approve"
    TIMELINE_READ = "timeline:read"
    APPROVALS_READ = "approvals:read"
    REPLAY_EXECUTE = "replay:execute"
    AGENTS_HEALTH = "agents:health"
    CRISIS_OVERRIDE = "crisis:override"
    DIAGNOSTICS_READ = "diagnostics:read"
    SESSION_READ = "session:read"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.READONLY: {
        Permission.SESSION_READ,
        Permission.TIMELINE_READ,
        Permission.APPROVALS_READ,
        Permission.DIAGNOSTICS_READ,
    },
    UserRole.OPERATOR: {
        Permission.SESSION_READ,
        Permission.FOUNDER_REQUEST,
        Permission.ACTION_PREPARE,
        Permission.TIMELINE_READ,
        Permission.APPROVALS_READ,
        Permission.REPLAY_EXECUTE,
        Permission.DIAGNOSTICS_READ,
    },
    UserRole.REVIEWER: {
        Permission.SESSION_READ,
        Permission.ACTION_APPROVE,
        Permission.TIMELINE_READ,
        Permission.APPROVALS_READ,
        Permission.DIAGNOSTICS_READ,
    },
    UserRole.ADMIN: {
        Permission.SESSION_READ,
        Permission.FOUNDER_REQUEST,
        Permission.ACTION_PREPARE,
        Permission.ACTION_APPROVE,
        Permission.TIMELINE_READ,
        Permission.APPROVALS_READ,
        Permission.REPLAY_EXECUTE,
        Permission.AGENTS_HEALTH,
        Permission.DIAGNOSTICS_READ,
    },
    UserRole.FOUNDER: set(Permission),
}

APPROVAL_LEVEL_BY_ROLE: dict[UserRole, int] = {
    UserRole.READONLY: 0,
    UserRole.OPERATOR: 1,
    UserRole.REVIEWER: 2,
    UserRole.ADMIN: 2,
    UserRole.FOUNDER: 4,
}
