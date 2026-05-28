import pytest

from core.permissions import Permission
from core.rbac import can_approve_level, role_has_permission
from core.roles import UserRole


def test_readonly_cannot_prepare():
    assert not role_has_permission(UserRole.READONLY, Permission.ACTION_PREPARE)


def test_readonly_has_session_read():
    assert role_has_permission(UserRole.READONLY, Permission.SESSION_READ)
    assert role_has_permission(UserRole.READONLY, Permission.DIAGNOSTICS_READ)


def test_operator_can_prepare_not_approve():
    assert role_has_permission(UserRole.OPERATOR, Permission.ACTION_PREPARE)
    assert role_has_permission(UserRole.OPERATOR, Permission.FOUNDER_REQUEST)
    assert role_has_permission(UserRole.OPERATOR, Permission.DIAGNOSTICS_READ)
    assert role_has_permission(UserRole.OPERATOR, Permission.SESSION_READ)
    assert not role_has_permission(UserRole.OPERATOR, Permission.ACTION_APPROVE)
    assert not can_approve_level(UserRole.OPERATOR, 3)


def test_reviewer_can_approve_not_founder_request():
    assert role_has_permission(UserRole.REVIEWER, Permission.ACTION_APPROVE)
    assert role_has_permission(UserRole.REVIEWER, Permission.DIAGNOSTICS_READ)
    assert role_has_permission(UserRole.REVIEWER, Permission.SESSION_READ)
    assert not role_has_permission(UserRole.REVIEWER, Permission.FOUNDER_REQUEST)
    assert not role_has_permission(UserRole.REVIEWER, Permission.REPLAY_EXECUTE)
    assert can_approve_level(UserRole.REVIEWER, 2)


def test_founder_can_approve_level_4():
    assert can_approve_level(UserRole.FOUNDER, 4)
